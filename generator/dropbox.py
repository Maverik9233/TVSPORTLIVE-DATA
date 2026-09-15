from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


# ============================================================
# TVSPORTLIVE - DROPBOX PUBLISHER
# ============================================================

DROPBOX_OAUTH_URL = (
    "https://api.dropboxapi.com/oauth2/token"
)

DROPBOX_UPLOAD_URL = (
    "https://content.dropboxapi.com/2/files/upload"
)

DROPBOX_REFRESH_TOKEN_ENV = (
    "TVSPORTLIVE_DROPBOX_REFRESH_TOKEN"
)

DROPBOX_APP_KEY_ENV = (
    "TVSPORTLIVE_DROPBOX_APP_KEY"
)

DROPBOX_APP_SECRET_ENV = (
    "TVSPORTLIVE_DROPBOX_APP_SECRET"
)

# App Folder root.
#
# Because the Dropbox application uses:
#
#   Scoped App (App Folder)
#
# "/" refers to the root of the TVSPORTLIVE-DATA
# application folder, NOT the user's entire Dropbox.
EVENTS_DROPBOX_PATH = "/events.txt"
LIVE_DROPBOX_PATH = "/live.txt"


class DropboxError(RuntimeError):
    """Errore durante autenticazione o pubblicazione su Dropbox."""


def _get_required_environment_variable(
    name: str,
) -> str:

    value = os.getenv(name, "").strip()

    if not value:
        raise DropboxError(
            f"Variabile/segreto '{name}' non configurato."
        )

    return value


def _get_credentials() -> tuple[str, str, str]:

    refresh_token = (
        _get_required_environment_variable(
            DROPBOX_REFRESH_TOKEN_ENV
        )
    )

    app_key = (
        _get_required_environment_variable(
            DROPBOX_APP_KEY_ENV
        )
    )

    app_secret = (
        _get_required_environment_variable(
            DROPBOX_APP_SECRET_ENV
        )
    )

    return (
        refresh_token,
        app_key,
        app_secret,
    )


def get_access_token() -> str:
    """
    Ottiene un access token Dropbox utilizzando
    il refresh token.

    Il refresh token non viene mai inviato
    al resto del programma e non viene scritto
    nei file generati.
    """

    (
        refresh_token,
        app_key,
        app_secret,
    ) = _get_credentials()

    credentials = (
        f"{app_key}:{app_secret}"
    )

    basic_auth = (
        credentials
        .encode("utf-8")
        .hex()
    )

    import base64

    basic_auth = base64.b64encode(
        credentials.encode("utf-8")
    ).decode("ascii")

    body = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        DROPBOX_OAUTH_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": (
                f"Basic {basic_auth}"
            ),
            "Content-Type": (
                "application/x-www-form-urlencoded"
            ),
            "User-Agent": (
                "TVSPORTLIVE-DataGenerator/1.0"
            ),
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=30,
        ) as response:

            raw_response = response.read()

    except urllib.error.HTTPError as error:

        error_body = error.read().decode(
            "utf-8",
            errors="replace",
        )

        raise DropboxError(
            "Autenticazione Dropbox fallita: "
            f"HTTP {error.code} - {error_body}"
        ) from error

    except urllib.error.URLError as error:

        raise DropboxError(
            "Impossibile raggiungere "
            "l'API Dropbox durante "
            "l'autenticazione."
        ) from error

    try:
        data = json.loads(
            raw_response.decode("utf-8")
        )

    except json.JSONDecodeError as error:

        raise DropboxError(
            "Risposta non valida ricevuta "
            "da Dropbox durante "
            "l'autenticazione."
        ) from error

    access_token = data.get(
        "access_token"
    )

    if not access_token:
        raise DropboxError(
            "Dropbox non ha restituito "
            "un access token valido."
        )

    return access_token


def upload_file(
    local_file: Path,
    dropbox_path: str,
    access_token: str,
) -> None:
    """
    Carica un file nella App Folder Dropbox.

    dropbox_path deve essere un percorso
    relativo alla root della App Folder.
    """

    if not local_file.exists():
        raise DropboxError(
            f"File locale non trovato: "
            f"{local_file}"
        )

    if not local_file.is_file():
        raise DropboxError(
            f"Il percorso non è un file: "
            f"{local_file}"
        )

    file_content = local_file.read_bytes()

    upload_arguments = {
        "path": dropbox_path,
        "mode": {
            ".tag": "overwrite"
        },
        "autorename": False,
        "mute": True,
        "strict_conflict": False,
    }

    request = urllib.request.Request(
        DROPBOX_UPLOAD_URL,
        data=file_content,
        method="POST",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            ),
            "Content-Type": (
                "application/octet-stream"
            ),
            "Dropbox-API-Arg": json.dumps(
                upload_arguments,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "User-Agent": (
                "TVSPORTLIVE-DataGenerator/1.0"
            ),
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=60,
        ) as response:

            raw_response = response.read()

    except urllib.error.HTTPError as error:

        error_body = error.read().decode(
            "utf-8",
            errors="replace",
        )

        raise DropboxError(
            "Upload Dropbox fallito: "
            f"{dropbox_path} - "
            f"HTTP {error.code} - "
            f"{error_body}"
        ) from error

    except urllib.error.URLError as error:

        raise DropboxError(
            "Impossibile raggiungere "
            "Dropbox durante l'upload "
            f"di {dropbox_path}."
        ) from error

    if not raw_response:
        raise DropboxError(
            "Dropbox ha restituito una "
            "risposta vuota durante "
            f"l'upload di {dropbox_path}."
        )

    try:
        response_data = json.loads(
            raw_response.decode("utf-8")
        )

    except json.JSONDecodeError as error:

        raise DropboxError(
            "Dropbox ha restituito una "
            "risposta non valida durante "
            f"l'upload di {dropbox_path}."
        ) from error

    returned_path = response_data.get(
        "path_display"
    )

    if returned_path:
        print(
            "Dropbox: aggiornato "
            f"{returned_path}"
        )
    else:
        print(
            "Dropbox: upload completato "
            f"per {dropbox_path}"
        )


def publish(
    events_file: Path,
    live_file: Path,
) -> None:
    """
    Pubblica events.txt e live.txt
    nella App Folder TVSPORTLIVE-DATA.

    channels.txt NON viene toccato.
    """

    access_token = get_access_token()

    upload_file(
        local_file=events_file,
        dropbox_path=EVENTS_DROPBOX_PATH,
        access_token=access_token,
    )

    upload_file(
        local_file=live_file,
        dropbox_path=LIVE_DROPBOX_PATH,
        access_token=access_token,
    )

    print(
        "Dropbox: pubblicazione completata."
    )


def publish_from_output(
    output_directory: Path,
) -> None:
    """
    Pubblica i file generati nella cartella output/.
    """

    events_file = (
        output_directory / "events.txt"
    )

    live_file = (
        output_directory / "live.txt"
    )

    if not events_file.exists():
        raise DropboxError(
            "output/events.txt non esiste. "
            "Generare prima events.txt."
        )

    if not live_file.exists():
        raise DropboxError(
            "output/live.txt non esiste. "
            "Generare prima live.txt."
        )

    publish(
        events_file=events_file,
        live_file=live_file,
    )
