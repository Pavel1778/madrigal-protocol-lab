# v1.1.0 — IP fragmentation, annotations, pairing, 14-slide deck

## Added
- IP fragmentation reassembly (IPv4 + IPv6, RFC 5722 for overlap)
- Researcher annotations (persisted in project)
- Request/response pairing with confidence and basis
- CSV / JSON Lines export of parsed messages
- 19 field types (float, varint, TLV, bitmask, string, array, padding, checksum, computed, conditional)
- Kaitai Struct export + standalone parser
- Wireshark PCAP export (--wireshark-pcap)
- Web interface (FastAPI + HTMX)
- Dark/light theme + i18n RU/EN in GUI

## Changed
- Rule registration: applied rule now copied to rules/ and indexed in manifest.json (R5 fix)
- Defense script rewritten for 14-slide deck (5-min and 10-min routes)
- README: stack justification section, IPv6/fragmentation claims fixed
- DEFENSE_CHECKLIST: synced with actual test count
- Presentation: Madrigal branding, layout polish, typography

## Fixed
- Stale claims in README/docs about IPv6 and fragmentation
- Stale test counts (781/806/838 → 840)
- .gitignore hygiene (agent paths moved to .git/info/exclude)

## Verified
- tshark cross-check: 11/12 captures byte-for-byte, 1 explained (missing segment marker)
- 840 tests passing, ruff clean, CI green
- Real corpus: 45 requests + 45 responses, precision 1.00
