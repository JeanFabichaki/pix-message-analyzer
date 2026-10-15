"""Gera o dataset sintético (PT-BR) de mensagens de Pix para fine-tuning do Laya.

Pergunta treinada = a MESMA que o pix-gateway-service envia ao Laya:
    {"threat": {"type": "choice", "criteria": {"threat": "ameaça", "safe": "agradecimento ou conversa normal"}}}

Anti-vazamento: cada pool de fragmentos é embaralhado com seed fixa e particionado
em treino (60%) / validação (15%) / teste (25%). Um fragmento do teste nunca aparece no treino.
Saída: train.jsonl, val.jsonl, test.jsonl (teste congelado, 7,5% ameaças como no vídeo).
"""
import json, random, re, sys, unicodedata
from pathlib import Path

SEED = 20261014
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "data")

# ----------------------------------------------------------------------------- pools
VIOLENCIA = [
    "vou te pegar na saída do trabalho", "sei onde você mora e vou aí hoje", "vou quebrar sua cara",
    "vou acabar com você", "você vai se arrepender de ter nascido", "vou arrebentar seu carro",
    "toma cuidado quando sair de casa", "vou mandar uns caras na sua casa", "se aparecer aqui eu te racho no meio",
    "dorme com um olho aberto", "vou fazer você sofrer", "você tem as horas contadas",
    "vou te achar nem que seja no inferno", "sei a escola dos seus filhos", "vou quebrar suas pernas",
    "da próxima vez que eu te ver eu te mato", "vai preparando o caixão", "vou dar um sumiço em você",
    "você vai pagar com sangue", "te espero na esquina com uns amigos", "vou te encher de porrada",
    "você não perde por esperar, vou te buscar", "vou colocar fogo na sua casa", "sua família vai pagar por isso",
    "vou te fazer engolir essas palavras na porrada", "te vejo na saída e você não vai gostar", "vou te matar",
    "já sei seu endereço, é questão de tempo", "vou dar um jeito em você e no seu filho", "nunca mais você anda em paz",
    "vou apagar você do mapa", "chega perto de mim de novo e eu te arrebento", "vou te caçar até você sumir",
    "vai ter troco e vai doer", "meus parceiros já sabem onde você trabalha, vão te visitar",
    "você vai ver o que eu faço com quem me trai", "eu sei a sua rotina, cuidado", "vai morrer, desgraçado",
    "te pego sozinho um dia desses", "vou fazer da sua vida um inferno",
]
EXIGENCIA = [
    "paga {v} agora", "manda um pix de {v} hoje", "deposita {v} aqui", "transfere {v} até as 18h",
    "quero {v} pra ficar calado", "faz o pix de {v}", "me passa {v} ainda hoje", "envia {v} nessa chave",
    "preciso de {v} em dinheiro agora", "cada semana é {v} de pix", "paga {v} que eu esqueço tudo", "manda {v} e a gente fica quites",
]
CHANTAGEM = [
    "senão eu mando suas fotos pra todo mundo", "ou eu conto tudo pra sua esposa", "ou eu vazo os prints da nossa conversa",
    "ou seu chefe fica sabendo do que você fez", "se não pagar eu espalho o vídeo", "senão eu exponho você nas redes sociais",
    "ou eu mostro os áudios pra sua família", "ou eu denuncio você falsamente", "se bloquear eu publico tudo",
    "caso contrário todo mundo vai ver suas fotos íntimas", "senão sua mãe vai ver o que você mandou pra mim",
    "ou eu posto suas conversas no grupo da firma", "senão eu acabo com a sua reputação", "ou vou na sua faculdade contar tudo",
    "senão o vídeo vai parar na internet", "ou eu conto seu segredo pra todo mundo da empresa",
    "cada dia que passa o preço sobe e as fotos saem", "ou eu entrego seu CPF pra uns caras que você não quer conhecer",
]
CONSEQUENCIA = [
    "senão vai ter problema pro seu lado", "ou você vai se arrepender", "ou eu vou aí resolver do meu jeito",
    "ou vai sobrar pra sua família", "senão eu perco a paciência e você vai ver", "ou o pessoal vai te procurar",
    "senão as consequências vão ser feias", "ou eu apareço no seu serviço e faço um escândalo",
    "senão eu vou até a casa da sua mãe", "ou eu mando uns amigos conversar com você", "senão sei onde te achar",
    "ou você paga ou você não anda mais tranquilo", "senão vai pagar mais caro, e não é só em dinheiro",
    "ou eu quebro tudo na sua loja", "ou você nunca mais vai dormir em paz",
]
COBRANCA_AGRESSIVA = [  # frases inteiras de cobrança com ameaça
    "última chance pra pagar antes de eu resolver do meu jeito", "não me faça ir aí cobrar pessoalmente",
    "paga o que deve ou vai ter problema pro seu lado", "melhor pagar antes que eu perca a paciência",
    "o pessoal vai te procurar se você não pagar", "sei seu endereço, paga logo",
    "toda vez que atrasar eu vou aí e você não vai gostar", "vou na casa da sua mãe cobrar se não pagar",
    "se não pagar hoje as consequências vão ser feias", "quem deve a mim não dorme tranquilo",
    "sua dívida, seu problema, e eu sei onde você mora", "paga ou eu mando alguém buscar",
]

PAGAMENTOS = [
    "pagamento do aluguel de outubro", "obrigado pelo almoço", "rachando a pizza de ontem", "valeu pela carona",
    "conta de luz do mês", "mesada do mês", "troco do mercado", "presente de aniversário", "um cafezinho pra você",
    "dívida quitada, obrigado", "pagando o que te devia", "conta do bar de sábado", "uber de volta", "vaquinha do churrasco",
    "material da escola", "pix do freela, bom trabalho", "feliz natal, família", "obrigada por tudo", "doação para a campanha",
    "ração do pet", "parcela do consórcio", "reembolso da viagem", "pagamento da faxina", "conserto da bike", "mensalidade da academia",
    "condomínio de outubro", "compra do feirante", "ingresso do show", "cota do presente da turma", "internet do mês",
    "gasolina da viagem", "salário da diarista", "lanche da tarde", "dízimo", "acerto da conta do restaurante", "remédio da vovó",
    "pagamento do dentista", "empréstimo devolvido, valeu mesmo", "troco do táxi", "pix da vaquinha do casamento",
    "livro que você me emprestou, comprei outro pra você", "mensalidade da escolinha", "assinatura do streaming dividida",
]
IDIOMAS_VIOLENTOS = [  # hard negatives: soam agressivos, são inofensivos
    "tô morrendo de saudade, vem me ver", "você mata a pau no futebol", "arrasou na apresentação, mandou muito",
    "vou te matar de rir com essa foto", "matei a aula hoje kkk", "esse bolo tá de matar", "se eu perder o prazo meu chefe me mata kkk",
    "tô morto de cansaço, obrigado pela ajuda", "essa música explodiu minha cabeça, valeu a indicação", "você é a bomba da festa",
    "vou devorar esse bolo que você fez", "me desculpa, pode me matar", "quebrou meu galho demais", "vamos matar o tempo no café",
    "bati o carro mas tá tudo bem, pix pro conserto", "essa série mata a gente de chorar", "mandou bem demais, killer",
    "te encontro na saída do trabalho pra gente almoçar", "vou aí hoje te dar um abraço", "sei onde você mora, vou levar o bolo aí",
    "cuidado na estrada, me avisa quando chegar", "vou te pegar na rodoviária às 18h", "te espero na esquina do mercado",
    "esse treino me arrebentou kkk", "o jogo foi uma guerra, mas ganhamos", "vou acabar com essa fome com sua pizza",
    "você vai se arrepender de não ter ido na festa, foi demais", "tô te devendo a vida por esse favor",
    "dormi com um olho aberto vendo o filme de terror", "o chefe vai te matar de elogios", "matei a charada, valeu a dica",
    "vou quebrar o cofrinho pra te pagar", "já tô com a faca e o queijo na mão, bora jantar", "atirei pra todo lado mas fechei a venda, obrigado",
    "essa dor de cabeça tá me matando, compra um remédio pra mim", "explodi de feliz com a notícia", "vou te contar um segredo bom: passou no concurso!",
    "se você não vier eu fico triste, mas entendo", "vou contar pra sua mãe que você passou, parabéns!",
]
COBRANCA_EDUCADA = [
    "oi, lembra do valor do conserto? quando puder me manda", "pode me pagar essa semana? preciso fechar o mês",
    "se não puder pagar hoje sem problema, me avisa", "faltam 50 reais da vaquinha, quando der", "lembrete amigável: vence amanhã",
    "se não pagar até sexta o plano será cancelado, aviso automático", "boleto vence amanhã, evite juros", "caso não renove, você perde o desconto",
    "só lembrando do acerto do aluguel", "ei, consegue me devolver aquele valor? sem pressa", "aviso: cobrança da mensalidade referente a outubro",
    "se atrasar mais de 5 dias incide multa de 2%, conforme contrato", "me manda o comprovante quando fizer, por favor",
    "podemos parcelar o que você me deve, o que acha?",
]
NEUTRAS = [
    "ok", "pix teste", "oi", "ref 1234", "pagamento", "bom dia", ".", "enviado", "segue o valor", "conforme combinado", "boa tarde, tudo bem?",
    "como combinamos", "fechado", "obrigado!", "👍", "teste", "pedido 8821", "nota fiscal 3321", "parabéns pelo bebê!", "feliz aniversário!",
    "saudade de você", "te amo, bom dia", "chegou bem?", "depois me liga", "valeu irmão", "tmj", "até domingo", "bjs",
]

PREFIXOS_T = ["", "", "", "olha só: ", "escuta bem: ", "última vez: ", "ei, ", "presta atenção. ", "ultimo aviso: ", "então, "]
SUFIXOS_T = ["", "", "", "!!!", ".", "...", " 😡", " 😈", " entendeu?", " não me teste", " tô falando sério", " vc sabe que eu cumpro"]
PREFIXOS_S = ["", "", "", "", "oi, ", "e aí, ", "olá, ", "opa, ", "bom dia! ", "boa noite, "]
SUFIXOS_S = ["", "", "", "!", ".", " 🙏", " 😂", " kkk", " 😊", " ❤️", " valeu!", " abraço"]
VALORES = ["R$ 50", "100 reais", "R$ 200", "300", "R$ 500", "mil reais", "R$ 1.000", "2 mil", "R$ 5.000", "500 conto", "R$ 150"]


def split_pool(items, seed):
    items = sorted(set(items))
    r = random.Random(seed)
    r.shuffle(items)
    n = len(items)
    a, b = int(n * 0.60), int(n * 0.75)
    return {"train": items[:a], "val": items[a:b], "test": items[b:]}


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


LEET = str.maketrans({"a": "4", "e": "3", "o": "0", "i": "1", "s": "5"})


def noisy(s, r):
    p = r.random()
    if p < 0.12:
        s = s.lower()
    elif p < 0.18:
        s = s.upper()
    q = r.random()
    if q < 0.15:
        s = strip_accents(s)
    elif q < 0.20:  # leetspeak em palavras aleatórias
        s = " ".join(w.translate(LEET) if r.random() < 0.35 else w for w in s.split())
    elif q < 0.25:  # abreviações de internet
        s = s.replace("você", "vc").replace("não", "nao").replace("pra ", "p ").replace("quando", "qnd")
    return re.sub(r"\s+", " ", s).strip()[:140]


def make(split, pools, n_threat, n_safe, r):
    rows = []

    def threat_text():
        kind = r.choices(["violencia", "chantagem", "cobranca", "extorsao_violenta"], weights=[3, 4, 2, 2])[0]
        if kind == "violencia":
            return "violencia", r.choice(pools["violencia"][split])
        if kind == "chantagem":
            return "chantagem", f'{r.choice(pools["exigencia"][split]).format(v=r.choice(VALORES))} {r.choice(pools["chantagem"][split])}'
        if kind == "cobranca":
            return "cobranca_agressiva", r.choice(pools["cobranca_ag"][split])
        return "extorsao_violenta", f'{r.choice(pools["exigencia"][split]).format(v=r.choice(VALORES))} {r.choice(pools["consequencia"][split])}'

    def safe_text():
        kind = r.choices(["pagamento", "idioma", "educada", "neutra"], weights=[5, 3, 2, 1.5])[0]
        return {"pagamento": "pagamento", "idioma": "idioma_violento", "educada": "cobranca_educada", "neutra": "neutra"}[kind], r.choice(pools[kind][split])

    seen = set()
    for label, n, gen in (("threat", n_threat, threat_text), ("safe", n_safe, safe_text)):
        tries = 0
        while sum(1 for x in rows if x["label"] == label) < n and tries < n * 60:
            tries += 1
            cat, core = gen()
            pre = r.choice(PREFIXOS_T if label == "threat" else PREFIXOS_S)
            suf = r.choice(SUFIXOS_T if label == "threat" else SUFIXOS_S)
            if label == "safe" and cat == "pagamento" and r.random() < 0.5:
                core = f"{core} - {r.choice(VALORES)}"
            text = noisy(f"{pre}{core}{suf}", r)
            if not text or text in seen:
                continue
            seen.add(text)
            rows.append({"split": split, "text": text, "label": label, "category": cat})
    r.shuffle(rows)
    return rows


def main():
    r = random.Random(SEED)
    pools = {
        "violencia": split_pool(VIOLENCIA, 1), "exigencia": split_pool(EXIGENCIA, 2), "chantagem": split_pool(CHANTAGEM, 3),
        "consequencia": split_pool(CONSEQUENCIA, 4), "cobranca_ag": split_pool(COBRANCA_AGRESSIVA, 5),
        "pagamento": split_pool(PAGAMENTOS, 6), "idioma": split_pool(IDIOMAS_VIOLENTOS, 7),
        "educada": split_pool(COBRANCA_EDUCADA, 8), "neutra": split_pool(NEUTRAS, 9),
    }
    plan = {"train": (1200, 1800), "val": (140, 414), "test": (75, 925)}  # teste espelha o vídeo: 75 golpes + 925 normais
    OUT.mkdir(parents=True, exist_ok=True)
    all_seen, stats = set(), {}
    for split in ("test", "val", "train"):  # teste primeiro: nada do teste pode vazar para o treino
        rows = [x for x in make(split, pools, *plan[split], r) if x["text"] not in all_seen]
        all_seen.update(x["text"] for x in rows)
        with open(OUT / f"{split}.jsonl", "w", encoding="utf-8") as f:
            for i, x in enumerate(rows):
                f.write(json.dumps({"id": f"{split}-{i:05d}", **x}, ensure_ascii=False) + "\n")
        stats[split] = (len(rows), sum(x["label"] == "threat" for x in rows))
    print({k: {"n": v[0], "threat": v[1]} for k, v in stats.items()})


if __name__ == "__main__":
    main()
