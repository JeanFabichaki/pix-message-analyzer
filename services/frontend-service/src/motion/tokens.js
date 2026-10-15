// Tokens de movimento. Espelham --dur-* e --ease-snappy do index.css.
export const dur = {
  instant: 0.12,
  fast: 0.18,
  base: 0.32,
  slow: 0.6,
};

export const ease = [0.16, 1, 0.3, 1];

export const spring = {
  pop: { type: 'spring', stiffness: 500, damping: 30 },
  soft: { type: 'spring', stiffness: 260, damping: 26 },
};

// Ritmo da jornada (ms). A resposta real chega em poucos ms; isto é a "câmera lenta".
export const TEMPO = {
  send: 320,      // bolha sai do celular
  travel: 320,    // viagem entre estações
  analyze: 380,   // estação "analisando"
  verdict: 220,   // pausa após o veredito
  effect: 520,    // tempo extra nas estações com efeito (③ ⑤ ⑥) quando detectam algo
  deliver: 700,   // entrega e notificação
};

export const TEMPO_REDUCED = {
  send: 0,
  travel: 0,
  analyze: 140,
  verdict: 140,
  effect: 0,
  deliver: 160,
};
