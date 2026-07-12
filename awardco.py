"""AwardCo SFTP reward integration for BrewBot.

When a match is confirmed, BrewBot generates a small CSV row per employee and drops
it on AwardCo's SFTP server; AwardCo Connect picks it up and automatically issues 10
CrowdPoints. The file format is provisional (pending the AwardCo Connect call) and is
isolated in `_build_reward_rows()` so it can be adjusted in one place.

If SFTP isn't configured (no env vars) or the upload fails, `issue_points()` returns
False so the caller can fall back to manual code issuance via the admin channel.
"""

import io
import logging
import os
from datetime import datetime

log = logging.getLogger(__name__)

POINTS = 10

SFTP_HOST = os.getenv("AWARDCO_SFTP_HOST")
SFTP_USER = os.getenv("AWARDCO_SFTP_USER")
SFTP_KEY = os.getenv("AWARDCO_SFTP_KEY")
PROGRAM_ID = os.getenv("AWARDCO_PROGRAM_ID", "CROWDBREW_EARN")


def is_configured() -> bool:
    """True if all SFTP settings are present so an upload can be attempted."""
    return bool(SFTP_HOST and SFTP_USER and SFTP_KEY)


def _build_reward_rows(employee_ids: list[str], when: str) -> str:
    """Build the CSV body for a reward drop.

    FORMAT (pending AwardCo Connect confirmation):
        employee_id, program_id, points, date
    """
    header = "employee_id,program_id,points,date\n"
    lines = [f"{eid},{PROGRAM_ID},{POINTS},{when}" for eid in employee_ids]
    return header + "\n".join(lines) + "\n"


def issue_points(match_id: str, employee_ids: list[str]) -> bool:
    """Drop a reward file for the given employees on the AwardCo SFTP server.

    Returns True on a successful upload, False if SFTP is unconfigured or errors —
    in which case the caller should fall back to manual issuance.
    """
    if not is_configured():
        log.info("awardco SFTP not configured; skipping upload for match %s", match_id)
        return False

    when = datetime.utcnow().strftime("%Y-%m-%d")
    body = _build_reward_rows(employee_ids, when)
    remote_name = f"crowdbrew_{match_id}_{when}.csv"

    try:
        import paramiko

        key = paramiko.RSAKey.from_private_key_file(SFTP_KEY)
        transport = paramiko.Transport((SFTP_HOST, 22))
        transport.connect(username=SFTP_USER, pkey=key)
        try:
            sftp = paramiko.SFTPClient.from_transport(transport)
            sftp.putfo(io.BytesIO(body.encode("utf-8")), remote_name)
        finally:
            transport.close()
        log.info("awardco reward file dropped: %s (%d employees)", remote_name, len(employee_ids))
        return True
    except Exception:
        log.exception("awardco SFTP upload failed for match %s", match_id)
        return False
