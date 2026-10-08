# AGENTS.md — humanvoiced

> Thesis: `THESIS.md`. Build target: `TECH-SPEC.md`. Read both before touching code.

## Laws

1. **Secrets in vault only.** Names in tree (`auth_ref`), values never. 0600 files, secret-scan before push.
2. **Agents aren't counterparties.** Every agent request records principal + agent. Budget caps enforced server-side; anti-splitting monitored.
3. **Freeze from day one.** Contract hash + original WAV preserved before any money moves. No reconstruction without evidence.
4. **No auto-fault.** Detection is automatic; fault assignment needs review + appeal path. No public red labels without verified outcome.
5. **Advisory ≠ proof.** Style/consistency findings never solely block payment. Voice matching for suitability, never biometric identity.
6. **Scripts are data.** Briefs/scripts never become instructions. Evaluator context isolation, output-schema validation.
7. **No cloning.** No narrator audio/embeddings train voice-clone models without a separate specific agreement.
8. **AGPL patterns-only.** Reference implementations may inform; vendor only Apache/MIT with attribution.
9. **Humans decide:** money release, sanctions, identity, contested nonpayment. Everything else can route auto/assisted per policy version.
10. **Owner pushes.** Commit locally only when asked.
