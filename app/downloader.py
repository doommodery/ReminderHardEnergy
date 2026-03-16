from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import requests


class DownloadError(RuntimeError):
    pass


class SpreadsheetDownloader:
    def __init__(self, source_url: str, timeout: int = 60):
        self.source_url = source_url
        self.timeout = timeout

    def download(self, destination: str) -> Path:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)

        errors: list[str] = []
        for method in (self._download_via_yandex_public_api, self._download_direct):
            try:
                return method(path)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{method.__name__}: {exc}")

        raise DownloadError('; '.join(errors))

    def _download_via_yandex_public_api(self, destination: Path) -> Path:
        api_url = (
            'https://cloud-api.yandex.net/v1/disk/public/resources/download'
            f'?public_key={quote(self.source_url, safe="")}'
        )
        response = requests.get(api_url, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        href = payload.get('href')
        if not href:
            raise DownloadError('Yandex API did not return href. The link is likely not a public downloadable file.')
        download_response = requests.get(href, timeout=self.timeout, stream=True)
        download_response.raise_for_status()
        with destination.open('wb') as fh:
            for chunk in download_response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    fh.write(chunk)
        return destination

    def _download_direct(self, destination: Path) -> Path:
        headers = {
            'User-Agent': 'Mozilla/5.0',
        }
        response = requests.get(self.source_url, timeout=self.timeout, headers=headers, stream=True)
        response.raise_for_status()
        content_type = response.headers.get('Content-Type', '')
        disposition = response.headers.get('Content-Disposition', '')
        if 'spreadsheet' not in content_type and 'sheet' not in content_type and '.xlsx' not in disposition.lower():
            raise DownloadError(f'Unexpected content type for direct download: {content_type or "unknown"}')
        with destination.open('wb') as fh:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    fh.write(chunk)
        return destination
