import { useCallback, useEffect, useState } from "react";
import type { App } from "../../../lib/contract";
import { useAppEvents } from "../../../ui";
import { reasonOf } from "../../store";

/**
 * A list of apps read now and again on every `app` event (`space` "" = this computer's own; a
 * project's event names its space). `read` is the list call; a later answer replaces an earlier one.
 */
export function useAppList(space: string, read: () => Promise<App[]>, fallback: string) {
  const [apps, setApps] = useState<App[]>([]);
  const [problem, setProblem] = useState("");
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    try {
      const list = await read();
      setApps(Array.isArray(list) ? list : []);
      setProblem("");
    } catch (e) {
      setProblem(reasonOf(e, fallback));
    }
    setLoaded(true);
    // `read` is a fresh arrow each render; the space alone decides what is read
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [space]);

  useEffect(() => {
    void load();
  }, [load]);

  useAppEvents((e) => {
    if (e.type !== "app") return;
    if (e.space_id !== undefined && e.space_id !== space) return;
    void load();
  });

  /** Put one app's newest view in place (or at the end), without waiting for the event. */
  const put = useCallback((app: App) => {
    setApps((list) => (list.some((a) => a.app_id === app.app_id) ? list.map((a) => (a.app_id === app.app_id ? app : a)) : [...list, app]));
  }, []);
  const drop = useCallback((appId: string) => setApps((list) => list.filter((a) => a.app_id !== appId)), []);

  return { apps, problem, loaded, load, put, drop };
}
