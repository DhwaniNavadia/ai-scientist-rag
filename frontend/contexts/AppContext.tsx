"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { DEMO_PAPER_IDS } from "@/lib/demo-data";

const DEMO_STORAGE_KEY = "demo_mode";
const PAPER_STORAGE_KEY = "current_paper";

interface AppContextValue {
  /** Currently selected paper ID (null = none selected) */
  currentPaper: string | null;
  setCurrentPaper: (id: string | null) => void;
  /** List of available papers fetched from the API (or demo list in demo mode) */
  papers: string[];
  setPapers: (papers: string[]) => void;
  /** Demo mode flag */
  demoMode: boolean;
  toggleDemoMode: () => void;
}

const AppContext = createContext<AppContextValue>({
  currentPaper: null,
  setCurrentPaper: () => undefined,
  papers: [],
  setPapers: () => undefined,
  demoMode: false,
  toggleDemoMode: () => undefined,
});

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [currentPaper, _setCurrentPaper] = useState<string | null>(null);
  const [papers, setPapers] = useState<string[]>([]);
  const [demoMode, setDemoMode] = useState(false);

  // Wrap setCurrentPaper to also persist to localStorage
  const setCurrentPaper = useCallback((id: string | null) => {
    _setCurrentPaper(id);
    try {
      if (id) {
        localStorage.setItem(PAPER_STORAGE_KEY, id);
      } else {
        localStorage.removeItem(PAPER_STORAGE_KEY);
      }
    } catch {
      // localStorage not available
    }
  }, []);

  // Rehydrate demo mode and current paper from localStorage on mount
  useEffect(() => {
    try {
      const storedPaper = localStorage.getItem(PAPER_STORAGE_KEY);
      if (storedPaper) {
        _setCurrentPaper(storedPaper);
      }
      const stored = localStorage.getItem(DEMO_STORAGE_KEY);
      if (stored === "true") {
        setDemoMode(true);
        setPapers([...DEMO_PAPER_IDS]);
        _setCurrentPaper((prev) => prev ?? DEMO_PAPER_IDS[0]);
      }
    } catch {
      // localStorage not available (SSR / privacy mode)
    }
  }, []);

  const toggleDemoMode = useCallback(() => {
    setDemoMode((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(DEMO_STORAGE_KEY, String(next));
      } catch {
        // ignore
      }
      if (next) {
        setPapers([...DEMO_PAPER_IDS]);
        _setCurrentPaper((cp) => {
          const newPaper = cp ?? DEMO_PAPER_IDS[0];
          try { localStorage.setItem(PAPER_STORAGE_KEY, newPaper); } catch { /* */ }
          return newPaper;
        });
      } else {
        setPapers([]);
        _setCurrentPaper(null);
        try { localStorage.removeItem(PAPER_STORAGE_KEY); } catch { /* */ }
      }
      return next;
    });
  }, []);

  const value = useMemo(
    () => ({
      currentPaper,
      setCurrentPaper,
      papers,
      setPapers,
      demoMode,
      toggleDemoMode,
    }),
    [currentPaper, papers, demoMode, toggleDemoMode]
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  return useContext(AppContext);
}
