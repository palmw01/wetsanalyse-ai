"""De nodes van de agentgraaf, gegroepeerd per keten.

`build_graph` in `orchestrator.py` registreert ze; de gedeelde afhankelijkheden komen als één
expliciet `Bouw`-object mee in plaats van als vrije variabelen uit een omringende closure. Daardoor
is elke node los aanroepbaar — en dus los testbaar — zonder de hele graaf te bouwen.
"""
