import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { MotionConfig, useReducedMotion } from 'motion/react';

const STORAGE_KEY = 'pixguard:reduced-motion';
const MotionPrefsContext = createContext({ reduced: false, manualReduced: false, toggle: () => {} });

function readStored() {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === '1';
  } catch (e) {
    return false;
  }
}

function writeStored(value) {
  try {
    window.localStorage.setItem(STORAGE_KEY, value ? '1' : '0');
  } catch (e) {
    /* armazenamento indisponível: preferência vale só nesta sessão */
  }
}

export function MotionProvider({ children }) {
  const systemReduced = useReducedMotion();
  const [manualReduced, setManualReduced] = useState(false);

  useEffect(() => {
    setManualReduced(readStored());
  }, []);

  const toggle = useCallback(() => {
    setManualReduced((prev) => {
      writeStored(!prev);
      return !prev;
    });
  }, []);

  const reduced = Boolean(systemReduced) || manualReduced;

  useEffect(() => {
    document.documentElement.dataset.motion = reduced ? 'reduced' : 'full';
  }, [reduced]);

  const value = useMemo(() => ({ reduced, manualReduced, toggle }), [reduced, manualReduced, toggle]);

  return (
    <MotionPrefsContext.Provider value={value}>
      <MotionConfig reducedMotion={reduced ? 'always' : 'never'}>{children}</MotionConfig>
    </MotionPrefsContext.Provider>
  );
}

export function useMotionPrefs() {
  return useContext(MotionPrefsContext);
}
