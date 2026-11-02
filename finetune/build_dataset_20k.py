"""Gerador de Alta Capacidade para 20.000 Mensagens Sintéticas de Pix (PT-BR).

Expande as pools semânticas para cobrir com profundidade:
1. Violência física direta e ultimatos;
2. Extorsão financeira e chantagem (fotos íntimas, segredos, reputação);
3. Perseguição velada e Stalking (vigiar rotina, placas de carro, academia, saídas);
4. Marido / Ex-parceiro inconformado enviando ameaças contra a ex-esposa;
5. Cobrança agressiva e agiotagem hostil;
6. Tentativas reais de evasão, leetspeak e camuflagem;
7. Hard negatives avançados (gírias coloquiais, futebol, gaming, brigas inofensivas);
8. Pagamentos cotidianos, cobranças comerciais educadas e mensagens familiares.

Anti-vazamento: todos os fragmentos são particionados de forma estrita em Train (60%), Val (15%) e Test (25%).
Saída: data_20k/train.jsonl (15.000 msgs), data_20k/val.jsonl (2.500 msgs), data_20k/test.jsonl (2.500 msgs).
"""
import json
import random
import re
import sys
import unicodedata
from pathlib import Path

SEED = 20261024
ROOT_DIR = Path(__file__).resolve().parent
OUT_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else (ROOT_DIR / "data_20k")

# =============================================================================
# POOLS DE AMEAÇA
# =============================================================================

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
    "te pego sozinho um dia desses", "vou fazer da sua vida um inferno", "você não passa desta semana",
    "vou te estourar na bala se cruzar meu caminho", "se prepare que o seu fim tá próximo",
    "vou te moer no asfalto se aparecer aqui", "vai engolir dente se abrir essa boca",
    "sua cova já tá cavada seu verme", "vou te caçar até no quinto dos infernos",
    "vou mandar quebrar as duas pernas pra aprender", "vou tocar fogo no seu comércio com você dentro",
    "seus dias de folga acabaram, se prepara", "a gente resolve isso no ferro",
    "você vai sangrar pelo que fez comigo", "vou fazer questão de te destruir pessoalmente",
]

EXIGENCIA = [
    "paga {v} agora", "manda um pix de {v} hoje", "deposita {v} aqui", "transfere {v} até as 18h",
    "quero {v} pra ficar calado", "faz o pix de {v}", "me passa {v} ainda hoje", "envia {v} nessa chave",
    "preciso de {v} em dinheiro agora", "cada semana é {v} de pix", "paga {v} que eu esqueço tudo",
    "manda {v} e a gente fica quites", "transfere logo {v} sem chiar", "solta {v} na minha conta",
    "quero {v} até o meio-dia impreterivelmente", "manda {v} na hora ou o bicho vai pegar",
    "se vira e arruma {v} em 30 minutos", "faz o pix de {v} agora mesmo se quiser paz",
]

CHANTAGEM = [
    "senão eu mando suas fotos pra todo mundo", "ou eu conto tudo pra sua esposa", "ou eu vazo os prints da nossa conversa",
    "ou seu chefe fica sabendo do que você fez", "se não pagar eu espalho o vídeo", "senão eu exponho você nas redes sociais",
    "ou eu mostro os áudios pra sua família", "ou eu denuncio você falsamente", "se bloquear eu publico tudo",
    "caso contrário todo mundo vai ver suas fotos íntimas", "senão sua mãe vai ver o que você mandou pra mim",
    "ou eu posto suas conversas no grupo da firma", "senão eu acabo com a sua reputação", "ou vou na sua faculdade contar tudo",
    "senão o vídeo vai parar na internet", "ou eu conto seu segredo pra todo mundo da empresa",
    "cada dia que passa o preço sobe e as fotos saem", "ou eu entrego seu CPF pra uns caras que você não quer conhecer",
    "ou essas conversas confidenciais vão parar no grupo do RH", "senão sua noiva recebe os vídeos de ontem à noite",
    "se me ignorar vou mandar cópia do processo pra toda a vizinhança", "ou vaza tudo no canal do Telegram hoje mesmo",
]

CONSEQUENCIA = [
    "senão vai ter problema pro seu lado", "ou você vai se arrepender", "ou eu vou aí resolver do meu jeito",
    "ou vai sobrar pra sua família", "senão eu perco a paciência e você vai ver", "ou o pessoal vai te procurar",
    "senão as consequências vão ser feias", "ou eu apareço no seu serviço e faço um escândalo",
    "senão eu vou até a casa da sua mãe", "ou eu mando uns amigos conversar com você", "senão sei onde te achar",
    "ou você paga ou você não anda mais tranquilo", "senão vai pagar mais caro, e não é só em dinheiro",
    "ou eu quebro tudo na sua loja", "ou você nunca mais vai dormir em paz",
    "ou vai acordar sem teto e sem carro", "senão vou mandar uns cobradores pesados te visitarem",
    "ou a cobrança vai ser feita à base de ferro e fogo", "senão a próxima conversa será no necrotério",
]

COBRANCA_AGRESSIVA = [
    "última chance pra pagar antes de eu resolver do meu jeito", "não me faça ir aí cobrar pessoalmente",
    "paga o que deve ou vai ter problema pro seu lado", "melhor pagar antes que eu perca a paciência",
    "o pessoal vai te procurar se você não pagar", "sei seu endereço, paga logo",
    "toda vez que atrasar eu vou aí e você não vai gostar", "vou na casa da sua mãe cobrar se não pagar",
    "se não pagar hoje as consequências vão ser feias", "quem deve a mim não dorme tranquilo",
    "sua dívida, seu problema, e eu sei onde você mora", "paga ou eu mando alguém buscar na marra",
    "acha que agiota tem paciência de banco? paga hoje", "se eu tiver que bater na sua porta o juro dobra e você apanha",
    "te dou duas horas pra transferir o saldo ou seus bens vão virar fumaça", "caloteiro safado, sua hora tá chegando",
]

STALKING = [
    "vi você saindo da academia com o carro prata, vou te achar nem que seja no fim do mundo",
    "conheço seu trajeto diário, não me faça perder a paciência",
    "tô de olho em você todo santo dia, você não vai me escapar",
    "sei a placa do seu carro novo, não adianta tentar se esconder",
    "vi que você trocou de endereço, mas achou que eu não ia descobrir?",
    "estou te observando da janela do café em frente, não adianta fingir",
    "sei exatamente que horas você deixa as crianças na escola e fica sozinha",
    "passo na sua rua todo dia depois das 20h, qualquer hora a gente se esbarra",
    "seu prédio tem porteiro mas a garagem fica aberta, fica esperta",
    "vi você entrando no restaurante de camisa azul ontem, tô mais perto do que pensa",
    "não adianta mudar o número, eu sempre descubro onde você tá",
    "sei o modelo do seu carro e o caminho escuro que você faz voltando do trabalho",
    "tô sabendo onde você trabalha agora, vou fazer uma visita surpresa",
    "tirei foto sua no ponto de ônibus hoje de manhã, tô te cercando",
]

MARIDO_ABANDONADO_EX = [
    "se você não voltar comigo eu acabo com você e com quem tiver do seu lado",
    "acha que vai me largar e ficar em paz? vou infernizar sua vida até você voltar",
    "se eu te ver na rua com outro homem você vai se arrepender amargamente de ter me deixado",
    "você destruiu a nossa família ao sair de casa, agora vai pagar muito caro",
    "tô aqui na frente do seu prédio te vigiando, você não vai se livrar de mim tão fácil",
    "se você não me atender vou aparecer no seu trabalho e fazer o maior escândalo da sua vida",
    "se você me bloquear eu vou até a casa da sua mãe quebrar tudo",
    "ou você volta pra casa hoje ou eu tomo as crianças de você na marra",
    "você me abandonou e acha que vai ser feliz? eu vou te destruir aos poucos",
    "vou te perseguir onde quer que você vá, mulher nenhuma me abandona desse jeito",
    "se você arrumar outro cara eu mato ele e depois vou atrás de você",
    "você me deixou sem nada, agora prepare-se pra colher o que plantou",
    "vou infernizar cada minuto do seu dia até você se arrepender de ter pedido o divórcio",
    "não aceito você com outro, se você não for minha não vai ser de mais ninguém",
    "vou queimar todas as suas coisas que ficaram aqui se você não voltar agora",
    "saiu de casa achando que se livrou de mim? isso tá só começando",
    "se você for na delegacia o problema vai ser dez vezes pior pra você",
    "você vai voltar rastejando pra mim por bem ou por mal",
]

# =============================================================================
# POOLS BENIGNAS E NEGATIVOS DIFÍCEIS (HARD NEGATIVES)
# =============================================================================

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
    "pagamento dos uniformes", "compra de materiais para a reforma", "segunda parcela do curso de inglês",
    "conserto da máquina de lavar", "adiantamento da quinzena", "reembolso do combustível da van escolar",
    "pagamento da consulta com o oftalmologista", "pagamento dos exames de sangue laboratoriais",
    "rateio do churrasco da firma", "troca de óleo do veículo", "compra da ração para o cachorro",
]

IDIOMAS_VIOLENTOS = [  # Hard negatives: expressões coloquiais que soam violentas mas são inofensivas
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
    "vou te quebrar no FIFA hoje à noite kkk prepara o controle", "quase tive um infarto quando nosso time fez o gol",
    "esse preço que o mecânico cobrou foi uma facada danada", "esse hambúrguer artesanal é um tiro de tão bom",
    "nossa amizade é pra vida toda, mato e morro por você", "hoje eu tô só o pó da rabiola, que canseira",
    "vou te encher de beijo quando você chegar de viagem", "você arrebentou na prova da OAB, orgulho demais",
    "a gente brigou feito cão e gato ontem mas já fizemos as pazes amor", "vou te dar uma surra de carinho",
]

COBRANCA_EDUCADA = [
    "oi, lembra do valor do conserto? quando puder me manda", "pode me pagar essa semana? preciso fechar o mês",
    "se não puder pagar hoje sem problema, me avisa", "faltam 50 reais da vaquinha, quando der", "lembrete amigável: vence amanhã",
    "se não pagar até sexta o plano será cancelado, aviso automático", "boleto vence amanhã, evite juros", "caso não renove, você perde o desconto",
    "só lembrando do acerto do aluguel", "ei, consegue me devolver aquele valor? sem pressa", "aviso: cobrança da mensalidade referente a outubro",
    "se atrasar mais de 5 dias incide multa de 2%, conforme contrato", "me manda o comprovante quando fizer, por favor",
    "podemos parcelar o que você me deve, o que acha?", "lembrete: taxa condominial vence nesta quinta-feira",
    "olá prezado cliente, informamos a pendência da fatura anterior para regularização",
    "bom dia, segue a chave pix para quitação do débito negociado amigavelmente",
]

NEUTRAS = [
    "ok", "pix teste", "oi", "ref 1234", "pagamento", "bom dia", ".", "enviado", "segue o valor", "conforme combinado", "boa tarde, tudo bem?",
    "como combinamos", "fechado", "obrigado!", "👍", "teste", "pedido 8821", "nota fiscal 3321", "parabéns pelo bebê!", "feliz aniversário!",
    "saudade de você", "te amo, bom dia", "chegou bem?", "depois me liga", "valeu irmão", "tmj", "até domingo", "bjs",
    "código do pedido 44921", "ajuda de custo", "obrigado pela parceria", "tudo certo", "ótima semana pra você",
]

PREFIXOS_T = ["", "", "", "olha só: ", "escuta bem: ", "última vez: ", "ei, ", "presta atenção. ", "ultimo aviso: ", "então, "]
SUFIXOS_T = ["", "", "", "!!!", ".", "...", " 😡", " 😈", " entendeu?", " não me teste", " tô falando sério", " vc sabe que eu cumpro"]
PREFIXOS_S = ["", "", "", "", "oi, ", "e aí, ", "olá, ", "opa, ", "bom dia! ", "boa noite, "]
SUFIXOS_S = ["", "", "", "!", ".", " 🙏", " 😂", " kkk", " 😊", " ❤️", " valeu!", " abraço"]
VALORES = ["R$ 50", "100 reais", "R$ 200", "300", "R$ 500", "mil reais", "R$ 1.000", "2 mil", "R$ 5.000", "500 conto", "R$ 150", "20 reais"]

LEET = str.maketrans({"a": "4", "e": "3", "o": "0", "i": "1", "s": "5"})


def split_pool(items, seed):
    items = sorted(set(items))
    r = random.Random(seed)
    r.shuffle(items)
    n = len(items)
    a, b = int(n * 0.60), int(n * 0.75)
    return {"train": items[:a], "val": items[a:b], "test": items[b:]}


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def noisy(s, r):
    p = r.random()
    if p < 0.12:
        s = s.lower()
    elif p < 0.18:
        s = s.upper()
    q = r.random()
    if q < 0.15:
        s = strip_accents(s)
    elif q < 0.22:
        s = " ".join(w.translate(LEET) if r.random() < 0.35 else w for w in s.split())
    elif q < 0.30:
        s = s.replace("você", "vc").replace("não", "nao").replace("pra ", "p ").replace("quando", "qnd").replace("também", "tbm")
    return re.sub(r"\s+", " ", s).strip()[:140]


def make(split, pools, n_threat, n_safe, r):
    rows = []

    def threat_text():
        weights = [3, 3, 2, 2, 3, 4]  # violencia, chantagem, cobranca, extorsao, stalking, marido_abandonado
        kind = r.choices(
            ["violencia", "chantagem", "cobranca", "extorsao_violenta", "stalking", "marido_abandonado_ex"],
            weights=weights
        )[0]

        if kind == "violencia":
            return "violencia", r.choice(pools["violencia"][split])
        if kind == "chantagem":
            return "chantagem", f'{r.choice(pools["exigencia"][split]).format(v=r.choice(VALORES))} {r.choice(pools["chantagem"][split])}'
        if kind == "cobranca":
            return "cobranca_agressiva", r.choice(pools["cobranca_ag"][split])
        if kind == "extorsao_violenta":
            return "extorsao_violenta", f'{r.choice(pools["exigencia"][split]).format(v=r.choice(VALORES))} {r.choice(pools["consequencia"][split])}'
        if kind == "stalking":
            return "stalking", r.choice(pools["stalking"][split])
        return "marido_abandonado_ex", r.choice(pools["marido_ex"][split])

    def safe_text():
        kind = r.choices(["pagamento", "idioma", "educada", "neutra"], weights=[5, 3.5, 2, 1.5])[0]
        mapping = {
            "pagamento": "pagamento",
            "idioma": "idioma_violento",
            "educada": "cobranca_educada",
            "neutra": "neutra"
        }
        return mapping[kind], r.choice(pools[kind][split])

    seen = set()
    for label, n, gen in (("threat", n_threat, threat_text), ("safe", n_safe, safe_text)):
        tries = 0
        while sum(1 for x in rows if x["label"] == label) < n and tries < n * 120:
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
    print(f"=== GERANDO DATASET DE 20.000 MENSAGENS EM: {OUT_DIR} ===")
    r = random.Random(SEED)
    pools = {
        "violencia": split_pool(VIOLENCIA, 1),
        "exigencia": split_pool(EXIGENCIA, 2),
        "chantagem": split_pool(CHANTAGEM, 3),
        "consequencia": split_pool(CONSEQUENCIA, 4),
        "cobranca_ag": split_pool(COBRANCA_AGRESSIVA, 5),
        "stalking": split_pool(STALKING, 6),
        "marido_ex": split_pool(MARIDO_ABANDONADO_EX, 7),
        "pagamento": split_pool(PAGAMENTOS, 8),
        "idioma": split_pool(IDIOMAS_VIOLENTOS, 9),
        "educada": split_pool(COBRANCA_EDUCADA, 10),
        "neutra": split_pool(NEUTRAS, 11),
    }

    # Distribuição total = 20.000 mensagens
    # Train: 15.000 (6.000 ameaças, 9.000 normais = 40% ameaças)
    # Val: 2.500 (650 ameaças, 1.850 normais = calibração)
    # Test: 2.500 (188 ameaças, 2.312 normais = espelha 7,5% da taxa real)
    plan = {
        "test": (188, 2312),
        "val": (650, 1850),
        "train": (6000, 9000),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_seen = set()
    stats = {}

    for split in ("test", "val", "train"):
        n_threat, n_safe = plan[split]
        rows = [x for x in make(split, pools, n_threat, n_safe, r) if x["text"] not in all_seen]
        all_seen.update(x["text"] for x in rows)

        out_file = OUT_DIR / f"{split}.jsonl"
        with open(out_file, "w", encoding="utf-8") as f:
            for i, x in enumerate(rows):
                f.write(json.dumps({"id": f"{split}-{i:05d}", **x}, ensure_ascii=False) + "\n")

        stats[split] = (len(rows), sum(x["label"] == "threat" for x in rows))
        print(f" -> {split}.jsonl: {len(rows)} msgs ({stats[split][1]} ameaças, {len(rows) - stats[split][1]} normais)")

    # Copia o challenge.jsonl manual original para manter o benchmark de teste idêntico
    challenge_src = ROOT_DIR / "data" / "challenge.jsonl"
    challenge_dst = OUT_DIR / "challenge.jsonl"
    if challenge_src.is_file():
        challenge_dst.write_text(challenge_src.read_text(encoding="utf-8"), encoding="utf-8")
        print(f" -> challenge.jsonl copiado com sucesso ({len(challenge_dst.read_text().splitlines())} msgs manuais).")

    total_msgs = sum(s[0] for s in stats.values())
    print(f"\n✅ Concluído! Total gerado: {total_msgs} mensagens em {OUT_DIR}")


if __name__ == "__main__":
    main()
