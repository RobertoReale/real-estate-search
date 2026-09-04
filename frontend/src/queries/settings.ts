/** The settings: one read shared by the whole application, and the writes.
 *
 *  Two hooks read the same key for opposite reasons, and the difference is the
 *  point. The dashboard wants the saved settings as a fact — which sort options
 *  to offer, whether the listing reader exists — and must never see them change
 *  underneath it. The dialog is a *form* over the same fact, and a form that
 *  re-seeds itself from a background refetch throws away whatever the user was
 *  half way through typing. So the dashboard's copy never goes stale on its own,
 *  and the dialog asks for a fresh one exactly when it opens.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../services/api";
import type { Settings } from "../types";
import { keys } from "./keys";

/** The saved settings, read once and then only when something writes them.
 *  `staleTime: Infinity` is what keeps a background refetch out of an open form. */
export function useSettings() {
  return useQuery({
    queryKey: keys.settings,
    queryFn: () => api.getSettings(),
    staleTime: Infinity,
  });
}

/** The same settings, re-read every time the dialog opens.
 *
 *  A form seeded from a cached copy would be editing a snapshot, and the first
 *  save would write it back over whatever else had changed since. */
export function useSettingsForm() {
  return useQuery({
    queryKey: keys.settings,
    queryFn: () => api.getSettings(),
    staleTime: Infinity,
    refetchOnMount: "always",
  });
}

/** Persist the form. The server's answer is authoritative — it is what masks the
 *  secrets back out — so it replaces the cached copy rather than the payload. */
export function useSaveSettings() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<Settings>) => api.updateSettings(payload),
    onSuccess: (saved) => client.setQueryData(keys.settings, saved),
  });
}

export function useTelegramTest() {
  return useMutation({ mutationFn: () => api.telegramTest() });
}

export function useEmailTest() {
  return useMutation({ mutationFn: () => api.emailTest() });
}

/** Open a local browser at the portal and keep the cookie it earns. The stored
 *  timestamp and the "saved" placeholder come from the settings, so they are
 *  re-read when it lands. */
export function useDatadomeRefresh() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (portal: "immobiliare" | "idealista") => api.datadomeRefresh(portal),
    onSettled: () => client.invalidateQueries({ queryKey: keys.settings }),
  });
}

export function useCancelDatadomeRefresh() {
  return useMutation({ mutationFn: () => api.cancelDatadomeRefresh() });
}

/** Install one of the optional browser stacks. Which ones are available is part
 *  of the settings the backend reports, so that is re-read too. */
export function useInstallBrowser() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (which: "harvester" | "camoufox") =>
      which === "camoufox" ? api.installCamoufox() : api.installHarvester(),
    onSettled: () => client.invalidateQueries({ queryKey: keys.settings }),
  });
}

/** Prove a stored token is accepted. Deliberately not the shared query: this
 *  runs before the app is allowed to read anything, and a 200 is the whole
 *  answer it wants. */
export function useVerifyToken() {
  return useMutation({ mutationFn: () => api.getSettings() });
}
