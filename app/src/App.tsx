/**
 * su-app-01: the scaffold — pick a bundle, watch the decade, drag time.
 *
 * v0.1 surface: load a world bundle (file picker or server URL), verify its
 * seal client-side, render fan charts for a few headline assets with the
 * revealed path clipped at the reveal pointer, and step the pointer.
 *
 * The pointer here is DISPLAY state only (browse mode). The moment decisions
 * exist (su-app-02), the server's session pointer is the authority and this
 * control binds to it — that boundary is W5 and it is why this file keeps no
 * game logic.
 */

import { useCallback, useEffect, useState } from "react";
import { fetchBundle, parseBundle, type LoadedBundle } from "./lib/bundle";
import { cacheGet, cacheList, cachePut } from "./lib/idb";
import { cumulativeGrowth, FanChart } from "./components/FanChart";
import { Feed } from "./components/Feed";
import { Play } from "./Play";

const HEADLINE_ASSETS = ["equity", "bonds", "pe"] as const;

export default function App() {
  const [loaded, setLoaded] = useState<LoadedBundle | null>(null);
  const [revealed, setRevealed] = useState(0);
  const [cached, setCached] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    cacheList().then(setCached).catch(() => setCached([]));
  }, [loaded]);

  const openBytes = useCallback(async (bytes: ArrayBuffer, cacheKey?: string) => {
    try {
      const result = await parseBundle(bytes);
      if (cacheKey === undefined) {
        await cachePut(result.bundle.meta.run_id, bytes);
      }
      setLoaded(result);
      setRevealed(0);
      setError(null);
    } catch (e) {
      setError(String(e));
    }
  }, []);

  const openFile = useCallback(
    async (file: File) => openBytes(await file.arrayBuffer()),
    [openBytes],
  );

  const openCached = useCallback(
    async (runId: string) => {
      const bytes = await cacheGet(runId);
      if (bytes) await openBytes(bytes, runId);
    },
    [openBytes],
  );

  const openUrl = useCallback(async (url: string) => {
    try {
      const result = await fetchBundle(url);
      setLoaded(result);
      setRevealed(0);
      setError(null);
    } catch (e) {
      setError(String(e));
    }
  }, []);

  if (!loaded) {
    return (
      <main className="shell">
        <h1>Alternate Histories</h1>
        <p className="tagline">Load a world bundle to begin.</p>
        <input
          type="file"
          accept=".gz"
          onChange={(e) => e.target.files?.[0] && openFile(e.target.files[0])}
        />
        <UrlOpener onOpen={openUrl} />
        {cached.length > 0 && (
          <section>
            <h2>On this machine</h2>
            <ul>
              {cached.map((id) => (
                <li key={id}>
                  <button onClick={() => openCached(id)}>{id}</button>
                </li>
              ))}
            </ul>
          </section>
        )}
        {error && <p className="error">{error}</p>}
      </main>
    );
  }

  if (playing) {
    return <Play bundle={loaded.bundle} onExit={() => setPlaying(false)} />;
  }

  const { bundle, sealVerified } = loaded;
  const { months } = bundle.meta;
  const order = bundle.revealed.series_order;
  const column = (name: string) =>
    bundle.revealed.tape.map((row) => row[order.indexOf(name)]);

  return (
    <main className="shell">
      <header>
        <h1>{bundle.meta.title ?? bundle.meta.world_id}</h1>
        {bundle.meta.tagline && <p className="tagline">{bundle.meta.tagline}</p>}
        <p className="provenance">
          run <code>{bundle.meta.run_id.slice(0, 8)}</code> · seed {bundle.meta.seed} ·{" "}
          <span className={sealVerified ? "ok" : "bad"}>
            {sealVerified ? "tape seal verified" : "TAPE SEAL MISMATCH"}
          </span>{" "}
          ·{" "}
          <span className={bundle.meta.digest_verified ? "ok" : "bad"}>
            {bundle.meta.digest_verified ? "lineage verified" : "LINEAGE UNVERIFIED"}
          </span>
        </p>
      </header>

      <section className="time-control">
        <label>
          Month {revealed} / {months}
          <input
            type="range"
            min={0}
            max={months}
            value={revealed}
            onChange={(e) => setRevealed(Number(e.target.value))}
          />
        </label>
        <button onClick={() => setRevealed(Math.min(months, revealed + 12))}>
          +1 year
        </button>
        <button onClick={() => setPlaying(true)}>play this world</button>
        <button onClick={() => setLoaded(null)}>close</button>
      </section>

      {HEADLINE_ASSETS.map((asset) => (
        <FanChart
          key={asset}
          label={asset}
          bands={bundle.bands[asset]}
          revealed={cumulativeGrowth(column(asset))}
          revealedMonths={revealed}
        />
      ))}

      <Feed artifacts={bundle.feed.artifacts ?? []} revealedMonths={revealed} />
    </main>
  );
}

function UrlOpener({ onOpen }: { onOpen: (url: string) => void }) {
  const [url, setUrl] = useState("");
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (url) onOpen(url);
      }}
    >
      <input
        type="url"
        placeholder="…or a bundle URL"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
      />
      <button type="submit">load</button>
    </form>
  );
}
