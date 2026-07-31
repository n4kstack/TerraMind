from .agris import AgrisAdapter
from .faostat import FaostatAdapter
from .cgiar import CgiarAdapter
from .climate import ClimateAdapter
from .soil import SoilAdapter
from .agricola import AgricolaAdapter
from .pubag import PubAgAdapter
from .agecon import AgEconAdapter
from .openalex import OpenAlexAdapter
from .europepmc import EuropePmcAdapter

# CabiAdapter and AsabeAdapter are intentionally not registered:
#   - CABI  (cabidigitallibrary.org)  -> HTTP 403 on every request; the content
#     is subscription-gated and bot-protected, so it is unreachable without an
#     institutional entitlement.
#   - ASABE (elibrary.asabe.org)      -> resets the TCP connection on every
#     request; there is no public search endpoint.
# Both returned zero documents on every query. OpenAlex and Europe PMC cover
# the same supporting-research role with open APIs that return real abstracts.
# The modules remain in the tree so the adapters can be re-enabled if access
# is ever obtained.


def default_adapters():
    return [
        # Primary research: real abstracts, drives the evidence tier.
        AgricolaAdapter(),
        PubAgAdapter(),
        OpenAlexAdapter(),
        EuropePmcAdapter(),
        # Catalogue / dataset enrichment: context only, never primary evidence.
        AgrisAdapter(),
        FaostatAdapter(),
        CgiarAdapter(),
        ClimateAdapter(),
        SoilAdapter(),
        AgEconAdapter(),
    ]
