# Takedown policy

Publishing to the unmuzzle index is permissionless: any entry that passes
automated validation (schema, signature, live mirrors, key continuity)
merges without human review. Removal works the other way: human-reviewed,
transparent, and narrow.

## What gets an entry removed

- Illegal content or content that violates the host jurisdictions of the
  maintainer (GitHub/Cloudflare terms apply to the mirrors they operate).
- Malware or entries whose bytes do not match their own signed manifest.
- License violation: the entry's stated license does not permit
  redistribution of the files it points at.
- Publisher request: the holder of the org's signing key asks for removal.
- Key compromise: a proven compromise of an org's signing key. The org's
  entries are frozen until a rotation is established out of band.

## What does NOT get an entry removed

- Disagreement with the content. The index is a distribution layer, not an
  editorial board. If a mirror hosts it legally and the signature verifies,
  it stays.

## How to request

Open a GitHub issue titled `takedown: <org/name>` with the reason and
evidence. Removals are committed publicly to this repo, so the index's git
history is the permanent record of what was removed and why.

## Scope

Removal deletes the index entry (discovery), not the content. Mirrors and
torrents are controlled by their operators; the signature scheme exists
precisely so that no host, including this index, is the arbiter of bytes.
