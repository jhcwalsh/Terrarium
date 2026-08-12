/**
 * Provenance (su-gen-03) — the player-facing audit trail for generated worlds.
 *
 * Renders only when the bundle carries the su-gen-02 sections: the campaign
 * verdict line ("rearranged truth, and here is the audit trail") and the
 * per-factor proxy disclosure — which months of the underlying record are
 * reconstructed rather than observed, the datalab posture reaching the
 * player. equity_vol's HAR share renders separately from its VXO splice via
 * the by-rule split, as the sealed disclosure clause requires.
 *
 * Toy bundles have neither section; this component renders nothing for them.
 */

import type { WorldBundle } from "../lib/bundle";

export default function Provenance({ bundle }: { bundle: WorldBundle }) {
  const factors = bundle.factors;
  const cred = bundle.credibility;
  if (!factors && !cred) return null;

  const proxied = factors
    ? Object.entries(factors.proxy_shares)
        .filter(([, s]) => s.share > 0)
        .sort(([, a], [, b]) => b.share - a.share)
    : [];

  return (
    <details className="provenance-panel">
      <summary>Where this decade comes from</summary>
      {cred && (
        <p className="prov-verdict">
          Every month in this world is a real month from the historical record;
          only the sequence is new. Generator{" "}
          <code>{cred.generator_id ?? "?"}</code> · {cred.campaign} · verdict{" "}
          <strong>{cred.verdict}</strong> · data vintage{" "}
          <code>{cred.campaign_vintage_id ?? factors?.vintage_id ?? "?"}</code>
        </p>
      )}
      {proxied.length > 0 && (
        <>
          <p className="prov-note">
            Some underlying series are partly reconstructed rather than
            observed. Reconstructed shares of the 1953–2020 record, by factor:
          </p>
          <table className="prov-table">
            <thead>
              <tr>
                <th>factor</th>
                <th>reconstructed</th>
                <th>rule</th>
              </tr>
            </thead>
            <tbody>
              {proxied.map(([name, s]) => (
                <tr key={name}>
                  <td>{name}</td>
                  <td>{(s.share * 100).toFixed(1)}%</td>
                  <td>
                    {Object.entries(s.by_rule)
                      .map(([rule, share]) => `${rule} ${(share * 100).toFixed(1)}%`)
                      .join(" · ") || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </details>
  );
}
