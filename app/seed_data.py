"""Static data used by the seeder.

HSK level assignment rules (keep them in mind before editing the lists):
  * HSK1_3.0 -> the word is present in the "NEW(3.0) HSK 1 - 500 words" list
                (2021 distribution) that was used as the reference for this project.
                The revision effective from July 2026 has only 300 words at
                level 1, so some of these words may have moved to level 2.
  * HSK2_3.0 -> 公司 (listed in the HSK 2.0 level-2 list) and 程序 / 网络, which
                were classified at level 2 by the project owner. Not verified
                against the 2026 official list.
  * HSK_TECH -> technical vocabulary of IT, ERP and business, outside the HSK lists.
"""

from pathlib import Path
from typing import NamedTuple

from app.models import HSKLevel, TermCategory
from app.text_utils import HANZI_PATTERN

HANDWRITING_FILE = Path(__file__).parent / "data" / "handwriting_characters.txt"


class SeedTerm(NamedTuple):
    """One vocabulary entry to be inserted by the seeder."""

    portuguese: str
    hanzi: str
    pinyin: str
    category: TermCategory
    hsk_level: HSKLevel
    example_sentence: str
    example_translation: str


_CS = TermCategory.COMPUTER_SCIENCE
_AI = TermCategory.ARTIFICIAL_INTELLIGENCE
_SE = TermCategory.SOFTWARE_ENGINEERING
_ERP = TermCategory.ERP
_BIZ = TermCategory.BUSINESS
_GEN = TermCategory.GENERAL
_H1, _H2, _TECH = HSKLevel.HSK1, HSKLevel.HSK2, HSKLevel.TECH

SEED_TERMS: tuple[SeedTerm, ...] = (
    # ----------------------------- Technical vocabulary -----------------------------
    SeedTerm("Banco de dados", "数据库", "shùjùkù", _CS, _TECH,
             "我们使用数据库存储客户信息。", "Nós usamos um banco de dados para armazenar informações de clientes."),
    SeedTerm("Inteligência artificial", "人工智能", "réngōng zhìnéng", _AI, _TECH,
             "人工智能正在改变软件开发的方式。", "A inteligência artificial está mudando a forma como o software é desenvolvido."),
    SeedTerm("Programação", "编程", "biānchéng", _CS, _TECH,
             "我每天花两个小时学习编程。", "Eu passo duas horas por dia aprendendo programação."),
    SeedTerm("Planejamento de recursos empresariais (ERP)", "企业资源计划", "qǐyè zīyuán jìhuà", _ERP, _TECH,
             "公司上线了新的ERP系统来管理库存和财务。", "A empresa colocou no ar um novo sistema ERP para gerenciar estoque e finanças."),
    SeedTerm("Requisitos", "需求", "xūqiú", _SE, _TECH,
             "我们需要先和客户确认软件需求。", "Primeiro precisamos confirmar os requisitos de software com o cliente."),
    SeedTerm("Algoritmo", "算法", "suànfǎ", _CS, _TECH,
             "这个算法的时间复杂度很低。", "A complexidade de tempo deste algoritmo é baixa."),
    SeedTerm("Computação em nuvem", "云计算", "yúnjìsuàn", _CS, _TECH,
             "越来越多的企业把系统迁移到云计算平台。", "Cada vez mais empresas migram seus sistemas para plataformas de computação em nuvem."),
    SeedTerm("Aprendizado de máquina", "机器学习", "jīqì xuéxí", _AI, _TECH,
             "机器学习模型需要大量数据进行训练。", "Modelos de aprendizado de máquina precisam de grande quantidade de dados para treinamento."),
    SeedTerm("Cadeia de suprimentos", "供应链", "gōngyìngliàn", _ERP, _TECH,
             "ERP系统可以帮助企业优化供应链管理。", "O sistema ERP pode ajudar as empresas a otimizar a gestão da cadeia de suprimentos."),
    SeedTerm("Orçamento", "预算", "yùsuàn", _BIZ, _TECH,
             "这个项目的预算已经超支了。", "O orçamento deste projeto já estourou."),
    SeedTerm("Interface de programação de aplicações (API)", "应用程序接口", "yìngyòng chéngxù jiēkǒu", _SE, _TECH,
             "前端通过应用程序接口获取后端数据。", "O front-end obtém os dados do back-end por meio da API."),
    SeedTerm("Desenvolvimento ágil", "敏捷开发", "mǐnjié kāifā", _SE, _TECH,
             "我们团队采用敏捷开发，每两周发布一次新版本。", "Nossa equipe adota desenvolvimento ágil e lança uma nova versão a cada duas semanas."),
    SeedTerm("Dados", "数据", "shùjù", _CS, _TECH,
             "这个数据库里有很多数据。", "Este banco de dados tem muitos dados."),
    SeedTerm("Rede (de computadores)", "网络", "wǎngluò", _CS, _H2,
             "公司的网络很慢。", "A rede da empresa está lenta."),
    SeedTerm("Programa; procedimento", "程序", "chéngxù", _CS, _H2,
             "这个程序有一个错误。", "Este programa tem um erro."),
    SeedTerm("Programador", "程序员", "chéngxùyuán", _CS, _TECH,
             "我是一名程序员。", "Eu sou programador."),
    SeedTerm("Software", "软件", "ruǎnjiàn", _CS, _TECH,
             "这个软件很有用。", "Este software é muito útil."),
    SeedTerm("Servidor", "服务器", "fúwùqì", _CS, _TECH,
             "服务器今天不能用。", "O servidor está fora do ar hoje."),
    SeedTerm("Código (de programação)", "代码", "dàimǎ", _SE, _TECH,
             "请检查这段代码。", "Por favor, revise este trecho de código."),
    SeedTerm("Sistema", "系统", "xìtǒng", _CS, _TECH,
             "公司的系统需要升级。", "O sistema da empresa precisa ser atualizado."),
    SeedTerm("Corrigir; reparar", "修复", "xiūfù", _SE, _TECH,
             "我昨天修复了一个错误。", "Ontem eu corrigi um erro."),
    SeedTerm("Senha", "密码", "mìmǎ", _CS, _TECH,
             "请不要告诉别人你的密码。", "Por favor, não conte a sua senha a ninguém."),
    SeedTerm("Teste; testar", "测试", "cèshì", _SE, _TECH,
             "上线前必须先测试。", "É preciso testar antes de colocar no ar."),
    SeedTerm("Implantação; implantar", "部署", "bùshǔ", _SE, _TECH,
             "我们今天部署新版本。", "Hoje nós implantamos a nova versão."),
    SeedTerm("Empresa", "公司", "gōngsī", _BIZ, _H2,
             "我在一家软件公司工作。", "Eu trabalho em uma empresa de software."),
    # ------------------------------ HSK 3.0 - level 1 ------------------------------
    SeedTerm("Eu", "我", "wǒ", _GEN, _H1, "我是学生。", "Eu sou estudante."),
    SeedTerm("Você; tu", "你", "nǐ", _GEN, _H1, "你会写程序吗？", "Você sabe escrever programas?"),
    SeedTerm("Ele", "他", "tā", _GEN, _H1, "他在北京工作。", "Ele trabalha em Pequim."),
    SeedTerm("Nós", "我们", "wǒmen", _GEN, _H1, "我们明天开会。", "Nós temos reunião amanhã."),
    SeedTerm("Ser (cópula)", "是", "shì", _GEN, _H1, "这是我的电脑。", "Este é o meu computador."),
    SeedTerm("Ter; haver", "有", "yǒu", _GEN, _H1, "我有一个新手机。", "Eu tenho um celular novo."),
    SeedTerm("Não ter; não haver", "没有", "méiyǒu", _GEN, _H1, "我没有时间。", "Eu não tenho tempo."),
    SeedTerm("Não", "不", "bù", _GEN, _H1, "我不忙。", "Eu não estou ocupado."),
    SeedTerm("Muito", "很", "hěn", _GEN, _H1, "他今天很忙。", "Ele está muito ocupado hoje."),
    SeedTerm("Ocupado", "忙", "máng", _GEN, _H1, "你忙吗？", "Você está ocupado?"),
    SeedTerm("Bom", "好", "hǎo", _GEN, _H1, "这个电脑很好。", "Este computador é muito bom."),
    SeedTerm("Estar em; em", "在", "zài", _GEN, _H1, "我在家工作。", "Eu trabalho em casa."),
    SeedTerm("Partícula de ação concluída ou mudança", "了", "le", _GEN, _H1,
             "我昨天买了手机。", "Ontem eu comprei um celular."),
    SeedTerm("Computador", "电脑", "diànnǎo", _CS, _H1, "我的电脑坏了。", "Meu computador quebrou."),
    SeedTerm("Telefone; ligação", "电话", "diànhuà", _GEN, _H1, "请给我打电话。", "Por favor, me ligue."),
    SeedTerm("Celular", "手机", "shǒujī", _CS, _H1, "我的手机在桌子上。", "Meu celular está sobre a mesa."),
    SeedTerm("Acessar a internet", "上网", "shàngwǎng", _CS, _H1,
             "我今天上网学习汉语。", "Hoje eu fico online para estudar chinês."),
    SeedTerm("Online; na internet", "网上", "wǎngshang", _CS, _H1,
             "我在网上买东西。", "Eu compro coisas pela internet."),
    SeedTerm("Trabalho; trabalhar", "工作", "gōngzuò", _BIZ, _H1, "你在哪儿工作？", "Onde você trabalha?"),
    SeedTerm("Tempo", "时间", "shíjiān", _GEN, _H1, "你有时间吗？", "Você tem tempo?"),
    SeedTerm("Estudar", "学习", "xuéxí", _GEN, _H1, "我学习汉语和编程。", "Eu estudo chinês e programação."),
    SeedTerm("Fazer reunião", "开会", "kāihuì", _BIZ, _H1, "我们下午开会。", "Nós temos reunião à tarde."),
    SeedTerm("Ir trabalhar; começar o expediente", "上班", "shàngbān", _BIZ, _H1,
             "我八点上班。", "Eu começo a trabalhar às oito."),
    SeedTerm("Sair do trabalho; encerrar o expediente", "下班", "xiàbān", _BIZ, _H1,
             "他六点下班。", "Ele sai do trabalho às seis."),
    SeedTerm("Ontem", "昨天", "zuótiān", _GEN, _H1, "昨天我在公司。", "Ontem eu estava na empresa."),
    SeedTerm("Hoje", "今天", "jīntiān", _GEN, _H1, "今天天气很好。", "O tempo está ótimo hoje."),
    SeedTerm("Amanhã", "明天", "míngtiān", _GEN, _H1, "明天我去上班。", "Amanhã eu vou trabalhar."),
    SeedTerm("Agora", "现在", "xiànzài", _GEN, _H1, "现在我在工作。", "Agora eu estou trabalhando."),
    SeedTerm("Saber", "知道", "zhīdào", _GEN, _H1, "我不知道。", "Eu não sei."),
    SeedTerm("Entender", "明白", "míngbai", _GEN, _H1, "我明白了。", "Entendi."),
    SeedTerm("Escrever", "写", "xiě", _GEN, _H1, "我会写汉字。", "Eu sei escrever caracteres chineses."),
    SeedTerm("Abrir; ligar", "打开", "dǎkāi", _CS, _H1, "请打开电脑。", "Por favor, ligue o computador."),
    SeedTerm("Fechar; desligar", "关上", "guānshang", _CS, _H1, "他关上了电脑。", "Ele desligou o computador."),
    SeedTerm("Usar", "用", "yòng", _GEN, _H1, "我用电脑工作。", "Eu uso o computador para trabalhar."),
    SeedTerm("Perguntar", "问", "wèn", _GEN, _H1, "我想问你。", "Eu quero te perguntar."),
    SeedTerm("Responder", "回答", "huídá", _GEN, _H1, "请回答我。", "Por favor, responda-me."),
    SeedTerm("Memorizar; lembrar-se de", "记住", "jìzhù", _GEN, _H1,
             "请记住我的名字。", "Por favor, lembre-se do meu nome."),
    SeedTerm("Encontrar", "找到", "zhǎodào", _GEN, _H1, "我找到了我的手机。", "Eu encontrei o meu celular."),
    SeedTerm("Errado; erro", "错", "cuò", _GEN, _H1, "这个字错了。", "Este caractere está errado."),
    SeedTerm("Importante", "重要", "zhòngyào", _GEN, _H1, "时间很重要。", "O tempo é importante."),
    SeedTerm("Preparar", "准备", "zhǔnbèi", _GEN, _H1, "我在准备考试。", "Estou me preparando para a prova."),
    SeedTerm("Útil", "有用", "yǒuyòng", _GEN, _H1, "这个很有用。", "Isto é muito útil."),
    SeedTerm("Conhecimento", "知识", "zhīshi", _GEN, _H1, "他有很多知识。", "Ele tem muito conhecimento."),
)

# Meaning of every character used in SEED_TERMS ("meaning · radical X = description").
# The part after "radical" is only given when the semantic radical is certain.
CHARACTER_BLOCKS: dict[str, str] = {
    "我": "eu · radical 戈 = lança", "你": "você · radical 亻 = pessoa", "他": "ele · radical 亻 = pessoa",
    "们": "plural de pessoas · radical 亻 = pessoa", "是": "ser · radical 日 = sol",
    "有": "ter · radical 月 = carne", "没": "não ter · radical 氵 = água", "不": "não · radical 一 = um",
    "很": "muito · radical 彳 = passo", "忙": "ocupado · radical 忄 = coração", "好": "bom · radical 女 = mulher",
    "在": "estar em · radical 土 = terra", "了": "partícula de ação concluída",
    "电": "eletricidade", "脑": "cérebro · radical 月 = carne/órgão", "话": "fala · radical 讠 = fala",
    "手": "mão", "机": "máquina · radical 木 = madeira", "上": "em cima; subir", "网": "rede",
    "工": "trabalho; ferramenta", "作": "fazer · radical 亻 = pessoa", "时": "tempo · radical 日 = sol",
    "间": "intervalo · radical 门 = porta", "学": "estudar · radical 子 = criança", "习": "praticar",
    "开": "abrir", "会": "reunir; saber (fazer)", "班": "turma · radical 王 = jade", "下": "embaixo; descer",
    "昨": "ontem · radical 日 = sol", "天": "céu; dia · radical 大 = grande", "今": "hoje · radical 人 = pessoa",
    "明": "claro; amanhã · radical 日 = sol", "现": "agora; aparecer · radical 王 = jade",
    "知": "saber · radical 矢 = flecha", "道": "caminho · radical 辶 = caminhar", "白": "branco; claro",
    "写": "escrever · radical 冖 = cobertura", "打": "bater · radical 扌 = mão", "关": "fechar",
    "用": "usar", "问": "perguntar · radical 门 = porta", "回": "voltar; responder · radical 囗 = cerca",
    "答": "responder · radical 竹 = bambu", "记": "lembrar; anotar · radical 讠 = fala",
    "住": "morar; fixar · radical 亻 = pessoa", "找": "procurar · radical 扌 = mão",
    "到": "chegar · radical 刂 = faca", "错": "errado · radical 钅 = metal", "重": "pesado; importante",
    "要": "querer; importante · radical 覀 = cobertura", "准": "preciso; permitido", "备": "preparar",
    "识": "conhecer · radical 讠 = fala",
    "数": "número; dados · radical 攵 = bater", "据": "base; segundo · radical 扌 = mão",
    "库": "armazém · radical 广 = casa aberta", "人": "pessoa", "智": "sabedoria · radical 日 = sol",
    "能": "capacidade; poder", "编": "tecer; organizar · radical 纟 = seda", "程": "processo · radical 禾 = grão",
    "企": "empreender; empresa · radical 人 = pessoa", "业": "negócio; indústria",
    "资": "recursos · radical 贝 = concha/dinheiro", "源": "fonte · radical 氵 = água",
    "计": "calcular · radical 讠 = fala", "划": "planejar · radical 刂 = faca",
    "需": "necessitar · radical 雨 = chuva", "求": "pedir; procurar", "算": "calcular · radical 竹 = bambu",
    "法": "método; lei · radical 氵 = água", "云": "nuvem", "器": "aparelho · radical 口 = boca",
    "供": "fornecer · radical 亻 = pessoa", "应": "responder; aplicar · radical 广 = casa aberta",
    "链": "corrente; cadeia · radical 钅 = metal", "预": "antecipar · radical 页 = página/cabeça",
    "敏": "ágil · radical 攵 = bater", "捷": "rápido · radical 扌 = mão", "发": "emitir; desenvolver",
    "接": "conectar · radical 扌 = mão", "口": "boca; abertura", "序": "ordem · radical 广 = casa aberta",
    "络": "rede; malha · radical 纟 = seda", "员": "membro; funcionário · radical 口 = boca",
    "软": "macio · radical 车 = veículo", "件": "peça; item · radical 亻 = pessoa",
    "服": "servir; roupa · radical 月 = carne", "务": "serviço; tarefa · radical 力 = força",
    "代": "substituir · radical 亻 = pessoa", "码": "código; número · radical 石 = pedra",
    "系": "sistema; ligar", "统": "unificar · radical 纟 = seda", "修": "consertar · radical 亻 = pessoa",
    "复": "repetir; restaurar · radical 夂 = andar devagar", "密": "secreto; denso · radical 宀 = telhado",
    "测": "medir · radical 氵 = água", "试": "testar · radical 讠 = fala", "部": "parte; setor · radical 阝 = cidade",
    "署": "dispor; instalar · radical 罒 = rede", "公": "público; comum",
    "司": "gerenciar; departamento · radical 口 = boca",
}


def build_radical_breakdown(hanzi: str) -> list[str]:
    """Return the semantic blocks of a term, one entry per character.

    Example: "电脑" -> ["电 (eletricidade)", "脑 (cérebro · radical 月 = carne/órgão)"].

    Raises:
        KeyError: if a character has no entry in CHARACTER_BLOCKS (so that a new
                  seed term can never be inserted without its decomposition).
    """
    return [f"{char} ({CHARACTER_BLOCKS[char]})" for char in hanzi if HANZI_PATTERN.match(char)]


def load_handwriting_characters(path: Path = HANDWRITING_FILE) -> frozenset[str]:
    """Read the handwriting-required characters (书写字) from the data file."""
    if not path.exists():
        return frozenset()
    lines = (line for line in path.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("#"))
    return frozenset(char for line in lines for char in line if HANZI_PATTERN.match(char))
