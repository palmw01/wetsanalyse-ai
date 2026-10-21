"""Async SQLAlchemy-Core laag: engine-beheer + tabeldefinities.

De datalaag is bewust **Core** (geen ORM): alle SQL is geïsoleerd in de service-modules
(profiles, users, gesprek_store, annotatie_v2_store, …), de domeinmodellen blijven plain Pydantic. De
types zijn portable – `JSON` wordt `JSONB` op PostgreSQL en gewone `JSON` op SQLite, zodat de
unit-tests op een in-memory SQLite draaien en productie op PostgreSQL.

De engine wordt lui geïnitialiseerd (lifespan in productie, fixture in tests) zodat de modules
zonder verbinding importeerbaar blijven.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    PrimaryKeyConstraint,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy import event
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import StaticPool

# JSONB op Postgres (indexeerbaar, efficiënt), gewone JSON op SQLite (tests).
_JSON = JSON().with_variant(JSONB(), "postgresql")
# Tijdzone-bewust opslaan; op Postgres = timestamptz. SQLite kent geen tz → normaliseer bij lezen
# (zie aware()), zodat .isoformat() altijd een offset (UTC) draagt.
_DT = DateTime(timezone=True)

metadata = MetaData()

# NB: de analyse-pijplijn en de wet-catalogus zijn verwijderd. De bijbehorende tabellen (`projects`,
# `rondes`, `llm_calls`, `app_settings`, `wet_catalogus`) worden niet meer gedefinieerd of aangemaakt;
# op een bestaande productie-DB blijven ze verweesd staan (samen met een eventuele Grafana-view erop)
# – het daadwerkelijk droppen is een aparte, bewuste migratie, niet iets dat hier stil bij de start gebeurt.

llm_profiles = Table(
    "llm_profiles",
    metadata,
    Column("name", String(128), primary_key=True),
    Column("provider", String(64), nullable=False, default="azure_ai"),
    Column("model", String(128), nullable=False, default=""),
    Column("api_base", String(512), nullable=False, default=""),
    Column("api_version", String(64), nullable=True),
    Column("output_strategy", String(64), nullable=False, default="prompt_and_parse"),
    Column("temperature", Float, nullable=False, default=0.0),
    Column("enc_api_key", Text, nullable=True),
    Column("is_default", Boolean, nullable=False, default=False),
    Column("updated_by", String(128), nullable=False, default=""),
    Column("created", _DT, nullable=False),
    Column("updated", _DT, nullable=False),
)

# Login-accounts voor de webapp. De API is de identiteitsbron; de frontend (Auth.js) houdt alleen
# de browsersessie. Inloggen gaat met de `userid` (de natuurlijke sleutel, lowercase genormaliseerd);
# `email` is een verplicht, uniek registratiegegeven (geen inlog-identiteit). Het TOTP-secret staat
# versleuteld (Fernet, zie secrets_crypto) en is optioneel (2FA staat standaard uit).
users = Table(
    "users",
    metadata,
    Column("userid", String(64), primary_key=True),
    Column("email", String(320), nullable=False, unique=True),
    Column("password_hash", Text, nullable=False),
    Column("role", String(16), nullable=False, default="analist"),
    Column("totp_secret_enc", Text, nullable=True),
    Column("totp_enabled", Boolean, nullable=False, default=False),
    Column("active", Boolean, nullable=False, default=True),
    # Sessie-epoch: JWT-sessies met een `loginAt` vóór deze tijd zijn ongeldig (revocatie bij
    # wachtwoordwijziging/-reset). NULL = nooit gewijzigd → geen revocatie.
    Column("sessions_valid_from", _DT, nullable=True),
    # Afwijkend tokenbudget voor deze gebruiker; NULL = volg `budget_beleid.tokens`. Additief
    # toegevoegd, dus `reconcile_schema` zet hem op een bestaande tabel bij (geen migratie) – zie de
    # toelichting bij `feedback_gezien_op` hieronder voor waarom de Column-declaratie ook dan nodig is.
    Column("token_budget", Integer, nullable=True),
    # Tijdstip waarop een beheerder de feedbacklijst voor het laatst bekeek; NULL = nooit.
    # Declaratief hier (nieuwe DB's via create_all) én idempotent via ALTER in reconcile_schema
    # (bestaande DB's). Zonder deze Column-declaratie crasht elke query die de kolom aanraakt met
    # AttributeError, ook al bestaat ze in de echte database – SQLAlchemy Core kent haar pas via
    # het Table-object.
    Column("feedback_gezien_op", _DT, nullable=True),
    # De laatst gebruikte TOTP-tijdstap (unix-tijd // 30). Een code geldt maar één keer: een stap
    # die niet groter is dan deze wordt geweigerd, ook binnen de ±30 s die `valid_window` toelaat.
    # NULL = nog nooit een code gebruikt. Additief, dus `reconcile_schema` zet hem bij.
    Column("totp_laatste_stap", BigInteger, nullable=True),
    Column("created", _DT, nullable=False),
    Column("updated", _DT, nullable=False),
)

# --- Zelfregistratie ------------------------------------------------------------
# Aanvragen voor een account. Een bezoeker vult naam, e-mail en een zelfgekozen wachtwoord in; het
# systeem leidt een userid af. Pas als een beheerder goedkeurt ontstaat er een rij in `users` – tot
# die tijd is dit geen account en kan er niet mee worden ingelogd. Het wachtwoord-hash staat hier al
# (bcrypt), zodat de goedgekeurde gebruiker meteen met zijn eigen wachtwoord kan inloggen en er geen
# tijdelijk wachtwoord hoeft te worden rondgestuurd.
#
# `email` is uniek: één openstaande aanvraag per adres. Afwijzen VERWIJDERT de rij (adres en
# volgnummer meteen weer vrij); een goedgekeurde aanvraag blijft staan als spoor en is met de hand
# op te ruimen.
registratie_aanvragen = Table(
    "registratie_aanvragen",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("voornaam", String(120), nullable=False, default=""),
    Column("achternaam", String(120), nullable=False, default=""),
    Column("email", String(320), nullable=False, unique=True),
    # Het afgeleide voorstel; de beheerder mag er bij het goedkeuren van afwijken.
    Column("userid_voorstel", String(64), nullable=False, default=""),
    Column("password_hash", Text, nullable=False, default=""),
    # aangevraagd | goedgekeurd (een afgewezen aanvraag wordt verwijderd, niet afgestempeld)
    Column("status", String(16), nullable=False, default="aangevraagd"),
    # Ongebruikt sinds afwijzen de rij verwijdert; blijft staan omdat `reconcile_schema` bewust
    # nooit kolommen dropt (dat is een aparte, bewuste migratie).
    Column("reden", Text, nullable=True),
    # De uiteindelijk toegekende userid; pas gevuld bij goedkeuring.
    Column("userid", String(64), nullable=True),
    Column("besloten_door", String(64), nullable=True),
    Column("besloten_op", _DT, nullable=True),
    Column("created", _DT, nullable=False),
    Column("updated", _DT, nullable=False),
    Index("ix_registratie_status_created", "status", "created"),
)

# --- Berichtensysteem -----------------------------------------------------------
# Release notes en aankondigingen: beheerders schrijven berichten (concept → gepubliceerd),
# analisten lezen ze. Leesbewijzen zijn (bericht, user)-paren.
berichten = Table(
    "berichten",
    metadata,
    Column("id",              Integer, primary_key=True, autoincrement=True),
    Column("titel",           Text, nullable=False, default=""),
    Column("inhoud",          Text, nullable=False, default=""),
    Column("type",            String(16), nullable=False, default="info"),
    Column("versie",          String(32), nullable=True),
    Column("gepubliceerd",    Boolean, nullable=False, default=False),
    Column("gepubliceerd_op", _DT, nullable=True),
    Column("aangemaakt_door", String(128), nullable=False, default=""),
    Column("created",         _DT, nullable=False),
    Column("updated",         _DT, nullable=False),
    Index("ix_berichten_gepubliceerd_created", "gepubliceerd", "created"),
)

bericht_leesbewijzen = Table(
    "bericht_leesbewijzen",
    metadata,
    Column("bericht_id", Integer, nullable=False),
    Column("userid",     String(64), nullable=False),
    Column("gelezen_op", _DT, nullable=False),
    PrimaryKeyConstraint("bericht_id", "userid"),
)

# Gebruikersfeedback vanuit de webapp. Elke rij is onwijzigbaar; beheerders lezen via
# /v1/admin/feedback.
user_feedback = Table(
    "user_feedback",
    metadata,
    Column("id",        Integer, primary_key=True, autoincrement=True),
    Column("client_id", String(128), nullable=False),
    Column("userid",    String(128), nullable=False),
    Column("categorie", String(32),  nullable=False),
    Column("tekst",     Text,        nullable=False),
    # Pad waar de feedback vandaan kwam, zodat een melding te plaatsen is.
    Column("pagina",    Text,        nullable=True),
    Column("created",   _DT,         nullable=False),
    Index("ix_user_feedback_created", "created"),
)

# Genereerbare API-tokens voor programmatische admin-toegang (bv. de admin-MCP), náást de
# statische env-admin-tokens. Alleen de sha256-HASH van het token wordt bewaard (hoog-entropie →
# geen bcrypt nodig); de plaintext wordt één keer bij aanmaken getoond en nergens opgeslagen. Het
# `token_prefix` dient enkel voor herkenning in de UI. Intrekken = `active=False` (geen delete-eis).
api_tokens = Table(
    "api_tokens",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("label", String(128), nullable=False, default=""),
    Column("token_hash", String(64), nullable=False, unique=True),
    Column("token_prefix", String(24), nullable=False, default=""),
    Column("scope", String(16), nullable=False, default="admin"),
    Column("active", Boolean, nullable=False, default=True),
    Column("created_by", String(128), nullable=False, default=""),
    Column("created", _DT, nullable=False),
    Column("last_used", _DT, nullable=True),
)

# --- Annotatie-domein: één laag per bronnode -----------------------------------
annotatie_v2_state = Table("annotatie_v2_state", metadata,
    Column("id", Integer, primary_key=True), Column("revisie", Integer, nullable=False, default=0))
annotatie_v2_snapshots = Table("annotatie_v2_snapshots", metadata,
    Column("id", String(128), primary_key=True), Column("inhoud", _JSON, nullable=False))
annotatie_v2_lagen = Table("annotatie_v2_lagen", metadata,
    Column("id", String(64), primary_key=True), Column("bron_iri", Text, nullable=False, unique=True),
    Column("revisie", Integer, nullable=False), Column("status", String(24), nullable=False),
    Column("snapshot_id", String(128), nullable=False), Column("geprojecteerd_revisie", Integer, nullable=False, default=0),
    Column("updated", _DT, nullable=False))
annotatie_v2_elementen = Table("annotatie_v2_elementen", metadata,
    Column("id", String(64), primary_key=True), Column("laag_id", String(64), nullable=False, index=True),
    Column("inhoud", _JSON, nullable=False))
annotatie_v2_batches = Table("annotatie_v2_batches", metadata,
    Column("id", String(128), primary_key=True), Column("payload_hash", String(64), nullable=False),
    Column("antwoord", _JSON, nullable=False))
annotatie_v2_dekking = Table("annotatie_v2_dekking", metadata,
    Column("id", String(64), primary_key=True), Column("bron_iri", Text, nullable=False, index=True),
    Column("snapshot_id", String(128), nullable=False), Column("inhoud", _JSON, nullable=False))
# `laag_id` is gezet waar een regel bij één laag hoort; de regel `revisie` (één per geraakte laag aan
# het eind van een schrijftransactie) maakt er de revisiehistorie per laag van. Oudere regels hebben
# hem niet – die laag heeft dan geen historie, geen verkeerde.
annotatie_v2_audit = Table("annotatie_v2_audit", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True), Column("element_id", String(64), nullable=True),
    Column("actor", String(64), nullable=False), Column("actie", String(40), nullable=False),
    Column("detail", _JSON, nullable=False), Column("tijdstip", _DT, nullable=False),
    Column("laag_id", String(64), nullable=True),
    Index("ix_annotatie_v2_audit_laag", "laag_id", "id"))

# --- Werkgebieden (spoor D, levering 1) ---------------------------------------
# Een werkgebied is een benoemde analyse met bronselecties. Gedeeld tussen analisten, net als de
# annotaties; wie wat deed staat in `werkgebied_audit`. Een werkgebied schrijft nooit annotaties:
# de inventaris leest de bestaande lagen. Archiveren en een selectie weghalen zijn soft (tijdstip),
# zodat de historie blijft kloppen.
werkgebieden = Table("werkgebieden", metadata,
    Column("id", String(64), primary_key=True),
    Column("naam", String(200), nullable=False),
    Column("analysevraag", Text, nullable=False, default=""),
    Column("afbakening", Text, nullable=False, default=""),
    # Startactiviteit a van de Leidraad (aanleiding, context, doel) en een gangbaar praktijkvoorbeeld
    # (activiteit 1b): het dossier waarop Lex zijn voorstellen voor dit werkgebied baseert.
    Column("aanleiding", Text, nullable=False, server_default="", default=""),
    Column("context", Text, nullable=False, server_default="", default=""),
    Column("doel", Text, nullable=False, server_default="", default=""),
    Column("praktijkvoorbeeld", Text, nullable=False, server_default="", default=""),
    Column("peildatum", String(10), nullable=True),
    Column("status", String(24), nullable=False, default="in_voorbereiding"),
    Column("revisie", Integer, nullable=False, default=1),
    Column("aangemaakt_door", String(64), nullable=False),
    Column("aangemaakt", _DT, nullable=False),
    Column("gewijzigd", _DT, nullable=False),
    Column("gearchiveerd", _DT, nullable=True),
    # Het samenstellen in het gesprek (activiteit 1) maakt een werkgebied met de id van die intake:
    # een tweede klik op *Aanmaken*, of een herhaling na een storing, levert hetzelfde werkgebied op.
    Column("intake_id", String(64), nullable=True),
    Index("ux_werkgebieden_intake", "intake_id", unique=True))
werkgebied_bronselecties = Table("werkgebied_bronselecties", metadata,
    Column("id", String(64), primary_key=True),
    Column("werkgebied_id", String(64), nullable=False, index=True),
    Column("bron_iri", Text, nullable=False),
    Column("bereik", String(16), nullable=False, default="onderliggend"),
    Column("rol", String(16), nullable=False, default="analyseren"),
    Column("reden", Text, nullable=False, default=""),
    Column("label", Text, nullable=False, default=""),
    Column("bwb_id", String(32), nullable=False, default=""),
    Column("snapshot_id", String(128), nullable=False, default=""),
    Column("bron_hash", String(64), nullable=False, default=""),
    Column("toegevoegd_door", String(64), nullable=False),
    Column("toegevoegd", _DT, nullable=False),
    Column("verwijderd", _DT, nullable=True))
werkgebied_audit = Table("werkgebied_audit", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("werkgebied_id", String(64), nullable=False),
    Column("actor", String(64), nullable=False),
    Column("actie", String(40), nullable=False),
    Column("detail", _JSON, nullable=False),
    Column("tijdstip", _DT, nullable=False),
    Index("ix_werkgebied_audit_werkgebied", "werkgebied_id", "id"))

# --- Begrippen (spoor D, levering 2) ------------------------------------------
# Een begrip hoort bij één werkgebied (het begrippenkader is impliciet: één per werkgebied). De inhoud
# staat als JSON; `begrip_revisies` bewaart per revisie een volledige kopie, want historie is hier een
# eis. Een koppeling verwijst naar een annotatie-element ZONDER foreign key en draagt haar eigen
# bewijsstand: elementen worden hard verwijderd, en een begrip mag zijn onderbouwing daar niet mee
# verliezen. Weghalen is soft (tijdstip).
begrippen = Table("begrippen", metadata,
    Column("id", String(64), primary_key=True),
    Column("werkgebied_id", String(64), nullable=False, index=True),
    Column("status", String(16), nullable=False, default="concept"),
    Column("revisie", Integer, nullable=False, default=1),
    Column("inhoud", _JSON, nullable=False),
    Column("aangemaakt_door", String(64), nullable=False),
    Column("aangemaakt", _DT, nullable=False),
    Column("gewijzigd", _DT, nullable=False),
    Column("geaccordeerd_door", String(64), nullable=True),
    Column("geaccordeerd_op", _DT, nullable=True),
    Column("geaccordeerd_revisie", Integer, nullable=True),
    Column("verwijderd", _DT, nullable=True))
begrip_revisies = Table("begrip_revisies", metadata,
    Column("begrip_id", String(64), primary_key=True),
    Column("revisie", Integer, primary_key=True),
    Column("actie", String(40), nullable=False),
    Column("detail", _JSON, nullable=False),
    Column("status", String(16), nullable=False),
    Column("inhoud", _JSON, nullable=False),
    Column("actor", String(64), nullable=False),
    Column("tijdstip", _DT, nullable=False))
begrip_koppelingen = Table("begrip_koppelingen", metadata,
    Column("id", String(64), primary_key=True),
    Column("begrip_id", String(64), nullable=False, index=True),
    Column("werkgebied_id", String(64), nullable=False, index=True),
    Column("element_id", String(64), nullable=False, index=True),
    Column("rol", String(16), nullable=False),
    Column("motivatie", Text, nullable=False, default=""),
    Column("bewijs", _JSON, nullable=False),
    Column("beoordeling", String(16), nullable=False, default="open"),
    Column("beoordeeld_door", String(64), nullable=True),
    Column("beoordeeld_op", _DT, nullable=True),
    Column("toegevoegd_door", String(64), nullable=False),
    Column("toegevoegd", _DT, nullable=False),
    Column("verwijderd", _DT, nullable=True),
    # Herbeoordeling (fase F1). `bewijs` blijft de stand van het koppelen en verandert nooit. Herkoppelen
    # aan een opvolger haalt deze koppeling weg en noemt de nieuwe hier; zo blijft de oude bewijsstand
    # als historie leesbaar. `bevestigingen` = [{element_hash, bron_hashes, door, op, motivatie}]: de
    # analist zag de veranderde passage en het begrip klopt nog – de nieuwste is de stand waartegen de
    # actualiteit daarna rekent. Additief, dus `reconcile_schema` zet ze bij.
    Column("vervangen_door", String(64), nullable=True),
    Column("bevestigingen", _JSON, nullable=True))
# Een element bewust buiten behandeling (fase F1, dekking): geen begrip nodig, met reden. Gedeeld zoals
# het werkgebied; terugdraaien is soft (tijdstip), zodat de audit en de rij het besluit bewaren.
werkgebied_element_besluiten = Table("werkgebied_element_besluiten", metadata,
    Column("id", String(64), primary_key=True),
    Column("werkgebied_id", String(64), nullable=False),
    Column("element_id", String(64), nullable=False),
    Column("stand", String(24), nullable=False, default="buiten_behandeling"),
    Column("reden", Text, nullable=False, default=""),
    Column("besloten_door", String(64), nullable=False),
    Column("besloten_op", _DT, nullable=False),
    Column("verwijderd", _DT, nullable=True),
    Index("ix_werkgebied_element_besluiten", "werkgebied_id", "element_id"))
# Deelvragen (vervolg op F, open keuze 4: optioneel). Een deelvraag splitst de analysevraag; ze is
# `actief`, of een `voorgesteld` voorstel van Lex dat de analist overneemt of `afgewezen` (dan stelt Lex
# hem niet opnieuw voor). Een actieve deelvraag hoort bij de scope en draagt dus de revisie van het
# werkgebied; een voorstel niet. Koppelingen naar bronselecties en begrippen zijn een set per deelvraag
# (`soort` bron | begrip), zonder foreign key, zoals de begripskoppelingen. Weghalen is soft.
werkgebied_deelvragen = Table("werkgebied_deelvragen", metadata,
    Column("id", String(64), primary_key=True),
    Column("werkgebied_id", String(64), nullable=False, index=True),
    Column("vraag", Text, nullable=False),
    Column("volgorde", Integer, nullable=False, default=0),
    Column("status", String(16), nullable=False, default="actief"),
    Column("herkomst", String(16), nullable=False, default="analist"),
    Column("reden", Text, nullable=False, default=""),
    # Bij een voorstel van Lex dat een actieve deelvraag verbetert: die deelvraag. Overnemen zet haar op
    # `vervangen`, en de opvolger krijgt haar plek en koppelingen.
    Column("vervangt", String(64), nullable=False, default="", server_default=""),
    Column("aangemaakt_door", String(64), nullable=False),
    Column("aangemaakt", _DT, nullable=False),
    Column("gewijzigd", _DT, nullable=False),
    Column("verwijderd", _DT, nullable=True))
werkgebied_deelvraag_koppelingen = Table("werkgebied_deelvraag_koppelingen", metadata,
    Column("deelvraag_id", String(64), primary_key=True),
    Column("soort", String(16), primary_key=True),
    Column("doel_id", String(64), primary_key=True),
    Column("gekoppeld_door", String(64), nullable=False),
    Column("gekoppeld", _DT, nullable=False))

# --- Bronnen vinden met Lex (spoor D, fase A) ---------------------------------
# Een bronnenrun past de ontdekmethoden van graph-qa toe op de selectie van een werkgebied. De api
# legt de invoer vast (kern- en contextbronnen, analysevraag), graph-qa zoekt en zet de kandidaten
# terug. Idempotent op (werkgebied, invoer): dezelfde selectie geeft dezelfde run.
# Een kandidaat is per (werkgebied, bron_iri) één rij: vinden meer methoden dezelfde bepaling, dan
# groeit zijn bewijs. Zijn besluit (later, uitgesloten met reden, opgenomen) blijft staan als een
# latere run hem opnieuw vindt – een uitgesloten kandidaat stelt Lex niet opnieuw voor.
bronnen_runs = Table("bronnen_runs", metadata,
    Column("id", String(64), primary_key=True),
    Column("werkgebied_id", String(64), nullable=False, index=True),
    Column("invoer_id", String(32), nullable=False),
    Column("invoer", _JSON, nullable=False),
    Column("status", String(16), nullable=False, default="wacht"),
    Column("meting", _JSON, nullable=True),
    Column("uitkomst_hash", String(64), nullable=True),
    Column("reden", Text, nullable=False, default=""),
    Column("gestart_door", String(64), nullable=False),
    Column("gestart", _DT, nullable=False),
    Column("gewijzigd", _DT, nullable=False),
    Index("ix_bronnen_runs_invoer", "werkgebied_id", "invoer_id"))
bron_kandidaten = Table("bron_kandidaten", metadata,
    Column("werkgebied_id", String(64), primary_key=True),
    Column("id", String(64), primary_key=True),
    Column("bron_iri", Text, nullable=False),
    Column("label", Text, nullable=False, default=""),
    Column("bwb_id", String(32), nullable=False, default=""),
    Column("rol", String(16), nullable=False),
    Column("bewijs", _JSON, nullable=False),
    Column("run_id", String(64), nullable=False),
    Column("status", String(16), nullable=False, default="voorgesteld"),
    Column("reden", Text, nullable=False, default=""),
    Column("besloten_door", String(64), nullable=True),
    Column("besloten_op", _DT, nullable=True),
    Column("voorgesteld", _DT, nullable=False),
    Column("gewijzigd", _DT, nullable=False))

# --- Voorstellen van Lex (spoor D, levering 3; ADR-004) -----------------------
# Een run is één toepassing van de begrippenketen op het manifest van een werkgebied. De api bouwt en
# bewaart het manifest (de vaste invoer), graph-qa rekent en zet de uitkomst terug. Idempotent op
# (werkgebied, manifest): dezelfde invoer geeft dezelfde groepen, dus een tweede start rekent niet
# opnieuw. Een groep-id is de inhoudshash van de keten (`G…`); een besluit over een groep (afgewezen,
# overgenomen) blijft daardoor staan als dezelfde groep in een latere run terugkomt.
begrippen_runs = Table("begrippen_runs", metadata,
    Column("id", String(64), primary_key=True),
    Column("werkgebied_id", String(64), nullable=False, index=True),
    Column("manifest_id", String(32), nullable=False),
    Column("manifest", _JSON, nullable=False),
    Column("overgeslagen", _JSON, nullable=False),
    Column("status", String(16), nullable=False, default="wacht"),
    Column("uitkomst", _JSON, nullable=True),
    Column("uitkomst_hash", String(64), nullable=True),
    Column("vragen_besluiten", _JSON, nullable=False),
    Column("reden", Text, nullable=False, default=""),
    Column("gestart_door", String(64), nullable=False),
    Column("gestart", _DT, nullable=False),
    Column("gewijzigd", _DT, nullable=False),
    # De model-laag (fase C): groepen, kaarten en oordelen na de verdieping; NULL = nog niet verdiept.
    Column("verdieping", _JSON, nullable=True),
    Index("ix_begrippen_runs_manifest", "werkgebied_id", "manifest_id"))
betekenisgroepen = Table("betekenisgroepen", metadata,
    Column("werkgebied_id", String(64), primary_key=True),
    Column("id", String(64), primary_key=True),
    Column("run_id", String(64), nullable=False),
    Column("leden", _JSON, nullable=False),
    Column("aandacht", String(8), nullable=False),
    Column("voorstel", _JSON, nullable=False),
    Column("uitleg", _JSON, nullable=False),
    Column("conflicten", _JSON, nullable=False),
    Column("besluit", String(16), nullable=False, default="open"),
    Column("reden", Text, nullable=False, default=""),
    Column("begrip_id", String(64), nullable=True),
    Column("besloten_door", String(64), nullable=True),
    Column("besloten_op", _DT, nullable=True),
    # Fase C: wie de groep vormde (de beslistabel of een oordeel van het model) en de concept-kaart.
    Column("door", String(8), nullable=False, server_default="regel"),
    Column("kaart", _JSON, nullable=True),
    # Fase D: leden die al een begrip werden terwijl de groep open bleef (splitsen). De groep toont
    # alleen de rest; zijn alle leden afgehandeld, dan is de groep overgenomen.
    Column("afgehandeld", _JSON, nullable=True))
# Eén afgeronde batch van de verdieping (fase C). Er staat alleen wat klaar is: een herstart doet de
# batches die hier ontbreken. De sleutel is inhoudelijk (graph-qa `verdieping.batch_id`), dus
# dezelfde batch met hetzelfde model en dezelfde prompt draait één keer.
begrippen_batches = Table("begrippen_batches", metadata,
    Column("run_id", String(64), primary_key=True),
    Column("id", String(64), primary_key=True),
    Column("werkgebied_id", String(64), nullable=False, index=True),
    Column("soort", String(8), nullable=False),          # vraag | kaart
    Column("ids", _JSON, nullable=False),                # kandidaat- of groep-id's
    Column("resultaat", _JSON, nullable=False),
    Column("model", String(128), nullable=False),
    Column("promptversie", String(32), nullable=False),
    Column("tokens", Integer, nullable=False, default=0),
    Column("gemaakt_door", String(64), nullable=False),
    Column("gemaakt", _DT, nullable=False))

# --- Lex naast de kaart (spoor D, fase E) -------------------------------------
# Een kaartrun is één actie van Lex op één begrip (brondefinitie zoeken, scherpere definitie,
# betekenisverschil, voorbeelden). De api legt de invoer vast – het begrip op zijn revisie, de dragende
# passages en het manifest van het werkgebied –, graph-qa rekent en zet de voorstellen terug. Een
# voorstel is een eigen rij, geen wijziging: pas overnemen door de analist raakt het begrip, en `basis`
# bewaart de waarde van het veld waarop het voorstel rust, zodat niets stil wordt overschreven.
begrip_kaartruns = Table("begrip_kaartruns", metadata,
    Column("id", String(64), primary_key=True),
    Column("werkgebied_id", String(64), nullable=False, index=True),
    Column("begrip_id", String(64), nullable=False, index=True),
    Column("actie", String(24), nullable=False),
    Column("invoer_id", String(32), nullable=False),
    Column("invoer", _JSON, nullable=False),
    Column("status", String(16), nullable=False, default="wacht"),
    Column("melding", Text, nullable=False, default=""),
    Column("meting", _JSON, nullable=True),
    Column("uitkomst_hash", String(64), nullable=True),
    Column("reden", Text, nullable=False, default=""),
    Column("gestart_door", String(64), nullable=False),
    Column("gestart", _DT, nullable=False),
    Column("gewijzigd", _DT, nullable=False),
    Index("ix_begrip_kaartruns_invoer", "begrip_id", "actie", "invoer_id"))
# --- Begripsrelaties (spoor D, fase F2) ----------------------------------------
# Een relatie tussen twee begrippen van één werkgebied, met type, richting en bewijs. Voorstellen van Lex
# (uit de relaties tussen elementen van de laatste klare begrippenrun) worden bij het lezen afgeleid; pas
# een besluit schrijft een rij, zodat een afgewezen voorstel niet terugkomt. `stand_van`/`stand_naar` =
# de hash van definitie + context van beide kanten bij het vastleggen: wijkt die af, dan staat de relatie
# in de herbeoordeling. `opvolging` (nieuwe betekenis, combineren) draagt in `bewijs` de vorige status
# van het vervangen begrip, zodat het verwijderen van de opvolger hem terugzet.
begrip_relaties = Table("begrip_relaties", metadata,
    Column("id", String(64), primary_key=True),
    Column("werkgebied_id", String(64), nullable=False, index=True),
    Column("van_begrip", String(64), nullable=False, index=True),
    Column("naar_begrip", String(64), nullable=False, index=True),
    Column("type", String(16), nullable=False),
    Column("herkomst", String(16), nullable=False),          # lex | analist | systeem
    Column("bewijs", _JSON, nullable=False),
    Column("toelichting", Text, nullable=False, default=""),
    Column("beoordeling", String(16), nullable=False),       # akkoord | afgewezen
    Column("stand_van", String(64), nullable=False, default=""),
    Column("stand_naar", String(64), nullable=False, default=""),
    Column("door", String(64), nullable=False),
    Column("op", _DT, nullable=False),
    Column("verwijderd", _DT, nullable=True))
begrip_voorstellen = Table("begrip_voorstellen", metadata,
    Column("id", String(64), primary_key=True),
    Column("werkgebied_id", String(64), nullable=False, index=True),
    Column("begrip_id", String(64), nullable=False, index=True),
    Column("run_id", String(64), nullable=False, index=True),
    Column("actie", String(24), nullable=False),
    Column("veld", String(16), nullable=False),           # definitie | uitleg | open_vragen | voorbeelden
    Column("volgorde", Integer, nullable=False, default=0),
    Column("basis", _JSON, nullable=False),               # {revisie, definitie, definitie_herkomst}
    Column("waarde", _JSON, nullable=False),
    Column("motivatie", Text, nullable=False, default=""),
    Column("aandacht", String(8), nullable=False, default="geel"),
    Column("aandachtspunten", _JSON, nullable=False),
    Column("door", _JSON, nullable=False),                # {bron: model|graaf, model, promptversie}
    Column("status", String(16), nullable=False, default="open"),
    Column("reden", Text, nullable=False, default=""),
    Column("besloten_door", String(64), nullable=True),
    Column("besloten_op", _DT, nullable=True),
    Column("begrip_revisie", Integer, nullable=True),     # de revisie die het overnemen opleverde
    Column("gemaakt", _DT, nullable=False))

# --- Tokenbudget --------------------------------------------------------------
# Verbruik is een JOURNAAL, geen teller. Eén rij per LLM-call; de stand van nu is een som over het
# huidige venster. Dat heeft drie eigenschappen die een teller niet heeft:
#
#   1. Een verwijderd gesprek raakt het verbruik niet. `gesprek_store.verwijder_gesprek` gooit de
#      berichten hard weg en `annotatie_v2_store.verwijder_weergave` haalt een annotatie weg;
#      daarom is `userid` hier de enige harde sleutel en zijn `gesprek_id`/`run_id` losse metadata
#      ZONDER foreign key. Wat er verbruikt is, is verbruikt – ook als het werk eruit gaat.
#   2. De reset vraagt geen cronjob: het vensterbegin wordt uit het anker gerekend (zie
#      `verbruik.venster_start`), dus er is geen periodieke handeling die kan mislukken of dubbel
#      draaien.
#   3. Elk getal is herleidbaar: "waar zijn mijn tokens heen" is een SELECT.
#
# Alleen inserts; nooit update/delete. De tijdlijn = ORDER BY id.
token_verbruik = Table(
    "token_verbruik",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("userid", String(64), nullable=False),
    # "agent" (een beurt van Lex) | "verbindingstest" (de admin-LLM-call)
    Column("bron", String(32), nullable=False, default=""),
    Column("model", String(128), nullable=False, default=""),
    # Bij Anthropic is `invoer` de NIET-gecachte rest: het volle promptvolume is
    # invoer + cache_lees + cache_schrijf. Alle vier apart bewaard, zodat een latere weging
    # (een cache-read kost ~0,1×) een rekenregel is en geen migratie.
    Column("invoer", Integer, nullable=False, default=0),
    Column("uitvoer", Integer, nullable=False, default=0),
    Column("cache_lees", Integer, nullable=False, default=0),
    Column("cache_schrijf", Integer, nullable=False, default=0),
    # Herkomst, puur als leesbare context. Geen foreign key – zie punt 1 hierboven.
    Column("gesprek_id", String(64), nullable=True),
    Column("run_id", String(64), nullable=True),
    Column("tijdstip", _DT, nullable=False),
    Index("ix_token_verbruik_user_tijd", "userid", "tijdstip"),
)

# Het budgetbeleid: één rij (id=1). Een tabel en geen env-knop, omdat de beheerder dit zonder
# redeploy moet kunnen wijzigen; de env levert alleen de beginwaarde bij de allereerste start
# (`verbruik.ensure_seeded`, hetzelfde patroon als bij de modelprofielen).
budget_beleid = Table(
    "budget_beleid",
    metadata,
    Column("id", Integer, primary_key=True),
    # Standaardbudget per venster; een gebruiker kan een eigen `users.token_budget` hebben.
    Column("tokens", Integer, nullable=False, default=500_000),
    Column("periode_dagen", Integer, nullable=False, default=7),
    # Vast startmoment. Alle vensters worden hiervandaan geteld, dus iedereen reset tegelijk en de
    # resetdatum is vooraf te noemen. Verschuif dit niet zonder reden: het verspringt ieders venster.
    Column("anker", _DT, nullable=False),
    # Uit = meten maar niet begrenzen (er wordt nog steeds geboekt).
    Column("actief", Boolean, nullable=False, default=True),
    Column("updated_by", String(128), nullable=False, default=""),
    Column("updated", _DT, nullable=False),
)


# --- Gesprekken-domein (chat-werkruimte) --------------------------------------
# Persistente chatgeschiedenis van de werkplek. Anders dan het annotatie-domein (client-gescopet,
# gedeeld) zijn gesprekken **per gebruiker** gescopet via `user_id` – de identiteit die de BFF uit de
# ingelogde sessie als vertrouwde `X-User-Id`-header meegeeft (nooit uit browser-input). Eén rij per
# gesprek; de berichten staan als aparte, geordende rijen (append-only in de praktijk: de UI voegt toe).
gesprekken = Table(
    "gesprekken",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(64), nullable=False, default=""),
    Column("titel", Text, nullable=False, default=""),
    Column("created", _DT, nullable=False),
    Column("updated", _DT, nullable=False),
    Index("ix_gesprekken_user_updated", "user_id", "updated"),
)

# De berichten binnen een gesprek. `inhoud` (JSON) draagt de heterogene payload van één beurt – de
# velden van `gesprek_contracts.BerichtInvoer` die niet leeg zijn (tekst, denk, bronnen, artefact,
# annotatie_doel, reeks, …; zie `gesprek_store._inhoud`). De tijdlijn = ORDER BY id.
gesprek_berichten = Table(
    "gesprek_berichten",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("gesprek_id", String(64), nullable=False),
    Column("rol", String(16), nullable=False, default="user"),
    Column("inhoud", _JSON, nullable=False, default=dict),
    # De idempotentiesleutel van een agent-beurt. Als eigen kolom (en niet alleen in `inhoud`)
    # kan de database afdwingen dat één run maar één bericht oplevert. Leeg voor berichten die niet
    # uit een run komen (de vraag van de gebruiker), vandaar de partiële index hieronder.
    Column("run_id", String(64), nullable=False, server_default="", default=""),
    Column("created", _DT, nullable=False),
    Index("ix_gesprek_berichten_gesprek", "gesprek_id", "id"),
    # Twee tabbladen kunnen op dezelfde run meekijken en de api draait op maxReplicas 3: een
    # check-then-insert dekt die race niet. Partieel, want lege run_ids zijn er veel.
    Index(
        "ux_gesprek_berichten_run",
        "run_id",
        unique=True,
        sqlite_where=text("run_id <> ''"),
        postgresql_where=text("run_id <> ''"),
    ),
)


# --- engine-beheer -------------------------------------------------------------

_engine: AsyncEngine | None = None


def init_engine(url: str, **kwargs) -> AsyncEngine:
    """(Her)initialiseer de globale async engine. Een in-memory SQLite-URL krijgt automatisch een
    StaticPool zodat alle verbindingen dezelfde database delen (anders is elke connectie leeg)."""
    global _engine
    # Normaliseer een kale Postgres-URL naar de async-driver. Zo is de connection-string die de
    # CloudNativePG-operator genereert (`postgresql://…`) rechtstreeks bruikbaar als DATABASE_URL.
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    elif url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    is_sqlite_mem = url.startswith("sqlite") and (":memory:" in url or url.endswith("://"))
    if is_sqlite_mem:
        kwargs.setdefault("poolclass", StaticPool)
        kwargs.setdefault("connect_args", {"check_same_thread": False})
    elif not url.startswith("sqlite"):
        kwargs.setdefault("pool_pre_ping", True)
    _engine = create_async_engine(url, **kwargs)
    event.listen(_engine.sync_engine, "commit", _na_commit)
    event.listen(_engine.sync_engine, "rollback", _na_rollback)
    return _engine


# --- Na de commit -----------------------------------------------------------------------------
# Een schrijfpad noteert op de verbinding wat er na de commit moet gebeuren (`noteer_na_commit`); een
# geregistreerde haak (`na_commit_haak`) krijgt het na de commit, een rollback gooit het weg. Zo hoeft
# niet elk schrijfpad zelf aan de projectie te denken (fase F3: elke audited werkgebiedmutatie). Het
# `commit`-event valt vóór de COMMIT op de database: een haak plant dus alleen werk in, en dat werk
# wacht met een leesslot tot de transactie echt klaar is (`begrip_projectie.projecteer`).
_NA_COMMIT = "wa_na_commit"
_haken: dict[str, Callable[[set], None]] = {}


def na_commit_haak(sleutel: str, haak: Callable[[set], None]) -> None:
    _haken[sleutel] = haak


def noteer_na_commit(conn, sleutel: str, waarde: str) -> None:
    """`conn` is een (Async)Connection; de notitie hangt aan de onderliggende DBAPI-verbinding."""
    sync = getattr(conn, "sync_connection", None) or conn
    sync.info.setdefault(_NA_COMMIT, {}).setdefault(sleutel, set()).add(waarde)


def _na_commit(conn) -> None:
    for sleutel, waarden in (conn.info.pop(_NA_COMMIT, None) or {}).items():
        haak = _haken.get(sleutel)
        if haak is not None:
            try:
                haak(waarden)
            except Exception:  # noqa: BLE001 – een haak mag een commit nooit laten falen
                logging.getLogger(__name__).warning("na_commit_haak_mislukt", extra={"sleutel": sleutel})


def _na_rollback(conn) -> None:
    conn.info.pop(_NA_COMMIT, None)


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("DB-engine niet geïnitialiseerd (roep db.init_engine aan in de lifespan).")
    return _engine


async def dispose_engine() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


async def create_all() -> None:
    """Maak de tabellen aan (tests + beproevingsfase; productie kan dit later via Alembic doen).
    Idempotent: alleen ONTBREKENDE tabellen worden aangemaakt."""
    async with get_engine().begin() as conn:
        await conn.run_sync(metadata.create_all)


def _ontbrekende_kolommen(sync_conn, tabel: Table) -> list[Column]:
    """Kolommen die in de definitie staan maar (nog) niet in de DB. Lege lijst als de tabel ontbreekt
    (die maakt `create_all` compleet aan)."""
    insp = sa_inspect(sync_conn)
    if not insp.has_table(tabel.name):
        return []
    bestaand = {c["name"] for c in insp.get_columns(tabel.name)}
    return [col for col in tabel.columns if col.name not in bestaand]


async def reconcile_schema() -> None:
    """Additieve kolom-migratie: voeg kolommen toe die in de tabeldefinitie staan maar in de DB
    ontbreken. `create_all` maakt alleen ontbrekende *tabellen*; zonder deze stap breekt een `SELECT`
    over een nieuw gedefinieerde kolom op een bestaande productie-tabel. **Alleen toevoegen** – nooit
    droppen of typewijzigen (dus dataverlies uitgesloten). Veilig op SQLite én Postgres; draait in de
    lifespan vóór het serveren."""
    engine = get_engine()
    preparer = engine.dialect.identifier_preparer
    async with engine.begin() as conn:
        for tabel in metadata.tables.values():
            for col in await conn.run_sync(_ontbrekende_kolommen, tabel):
                coltype = col.type.compile(dialect=engine.dialect)
                ddl = (
                    f"ALTER TABLE {preparer.format_table(tabel)} "
                    f"ADD COLUMN {preparer.format_column(col)} {coltype}"
                )
                # De server_default hoort mee: zonder DEFAULT krijgen bestaande rijen NULL, en dan
                # klopt niets wat op die kolom filtert. Een partiële index op `<> ''` sluit NULL
                # bijvoorbeeld stil uit (NULL <> '' is NULL, niet TRUE) en beschermt dan niets.
                if col.server_default is not None:
                    standaard = col.server_default.arg
                    ddl += f" DEFAULT {standaard!r}" if isinstance(standaard, str) else f" DEFAULT {standaard}"
                await conn.execute(text(ddl))
                await _na_kolom(conn, tabel, col)
        # Indexen komen niet uit `create_all` op een bestaande tabel; ze zijn idempotent aan te
        # maken en dat is precies wat een unieke constraint op een bestaande productietabel nodig
        # heeft.
        for tabel in metadata.tables.values():
            for index in tabel.indexes:
                await conn.run_sync(lambda sync_conn, ix=index: ix.create(sync_conn, checkfirst=True))


async def _na_kolom(conn, tabel, col) -> None:
    """Vul een net toegevoegde kolom waar de waarde al ergens anders stond.

    `run_id` leefde in de JSON-kolom `inhoud`. Zonder deze backfill zou de unieke index alleen
    nieuwe rijen beschermen, en zouden bestaande dubbelen onopgemerkt blijven bestaan.
    """
    if tabel.name != "gesprek_berichten" or col.name != "run_id":
        return
    dialect = conn.engine.dialect.name
    if dialect == "postgresql":
        haal = "COALESCE(inhoud->>'run_id', '')"
    else:  # sqlite
        haal = "COALESCE(json_extract(inhoud, '$.run_id'), '')"
    # Bestaande rijen hebben NULL (de DEFAULT geldt alleen voor nieuwe rijen op sommige versies);
    # allebei de gevallen meenemen.
    await conn.execute(text(
        f"UPDATE gesprek_berichten SET run_id = {haal} WHERE run_id IS NULL OR run_id = ''"))


def aware(dt: datetime | None) -> datetime | None:
    """Normaliseer een uit de DB gelezen datetime naar UTC-aware. SQLite geeft naïeve datetimes
    terug (geen tz-opslag); Postgres geeft al aware terug. Zo serialiseert .isoformat() altijd met
    offset en leest de browser de tijd niet als lokale tijd."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
