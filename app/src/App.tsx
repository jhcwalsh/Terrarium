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
import { fetchWorlds, WorldPicker, type WorldsDoc } from "./lib/worlds";
import type { Book, Plan } from "./lib/session";
import { cumulativeGrowth, FanChart } from "./components/FanChart";
import { Feed } from "./components/Feed";
import Provenance from "./components/Provenance";
import { BookEntry } from "./BookEntry";
import { ASSET_LABELS, Play } from "./Play";
import { RankedSetup, type PlayConfig } from "./RankedSetup";

type Mode = "browse" | "book" | "setup" | "play";

export default function App() {
  const [loaded, setLoaded] = useState<LoadedBundle | null>(null);
  const [revealed, setRevealed] = useState(0);
  const [cached, setCached] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>("browse");
  const [playConfig, setPlayConfig] = useState<PlayConfig | undefined>();
  const [worldsDoc, setWorldsDoc] = useState<WorldsDoc | null>(null);
  // su-app-06: the analyst's entered book/plan, set by BookEntry.onReady;
  // bookIsDefault gates ranked eligibility in RankedSetup and is carried
  // through to createSession via Play.
  const [book, setBook] = useState<Book | undefined>();
  const [plan, setPlan] = useState<Plan | undefined>();
  const [bookIsDefault, setBookIsDefault] = useState(true);

  useEffect(() => {
    cacheList().then(setCached).catch(() => setCached([]));
  }, [loaded]);

  useEffect(() => {
    // sib-01: progressive enhancement — a failed/missing /worlds (service
    // down, static hosting) just leaves the list empty; the picker/URL flow
    // below is unconditionally present either way.
    fetchWorlds()
      .then(setWorldsDoc)
      .catch(() => setWorldsDoc(null));
  }, []);

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
        <WorldPicker doc={worldsDoc} onOpen={openUrl} />
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

  if (mode === "book") {
    return (
      <BookEntry
        runId={loaded.bundle.meta.run_id}
        // su-app-06 (I3): re-entering book mode after a refused POST /sessions
        // restores what was typed. `book`/`plan` are already retained here for
        // createSession, so a refusal now costs a screen, not 210 fields.
        initialBook={book}
        initialPlan={plan}
        onReady={(b, p, isDefault) => {
          setBook(b);
          setPlan(p);
          setBookIsDefault(isDefault);
          setMode("setup");
        }}
        onCancel={() => setMode("browse")}
      />
    );
  }
  if (mode === "setup") {
    return (
      <RankedSetup
        bookIsDefault={bookIsDefault}
        onStart={(config) => {
          setPlayConfig(config);
          setMode("play");
        }}
        onCancel={() => setMode("browse")}
      />
    );
  }
  if (mode === "play") {
    return (
      <Play
        bundle={loaded.bundle}
        config={playConfig}
        book={book}
        plan={plan}
        onExit={() => setMode("browse")}
      />
    );
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
        <Provenance bundle={bundle} />
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
        <button onClick={() => setMode("book")}>play this world</button>
        <button onClick={() => setLoaded(null)}>close</button>
      </section>

      <div className="chart-grid">
        {ASSET_LABELS.filter(([key]) => bundle.bands[key]).map(([key, name]) => (
          <FanChart
            key={key}
            label={name}
            bands={bundle.bands[key]}
            revealed={cumulativeGrowth(column(key))}
            revealedMonths={revealed}
            height={190}
          />
        ))}
      </div>

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
