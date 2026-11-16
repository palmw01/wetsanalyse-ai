"""Gedeeld voor de poorttests."""
def pytest_configure(config):
    config.addinivalue_line("markers", "risico(id, laag=None): het risico van Lex Bench dat deze test dekt "
                                       "(docs/lex-bench/risicos.json, scripts/risicomatrix.py)")
