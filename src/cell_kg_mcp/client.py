from __future__ import annotations

import getpass
import warnings

from arango import ArangoClient
from arango.database import StandardDatabase

ARANGO_URL = "http://127.0.0.1:8530"
ARANGO_DATABASE = "Cell-KN-Phenotypes"
ARANGO_USERNAME = "nlm_ro"


def connect_arango() -> tuple[ArangoClient, StandardDatabase]:
    """Prompt for the password and connect through the running SSM tunnel."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        password = getpass.getpass(
            f"ArangoDB password for {ARANGO_USERNAME}: "
        )

    if not password:
        raise ValueError("The database password must not be empty.")

    driver = ArangoClient(
        hosts=ARANGO_URL,
        request_timeout=20,
    )

    try:
        database = driver.db(
            name=ARANGO_DATABASE,
            username=ARANGO_USERNAME,
            password=password,
            verify=True,
        )
    except Exception:
        driver.close()
        raise

    return driver, database
