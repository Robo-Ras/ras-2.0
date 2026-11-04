"""Interpreta o que foi dito: dicionário de palavras (e variações) -> comando.

O dicionário fica em comandos_voz.json (na raiz do projeto) e é o mesmo do painel (Chrome).
Formato de uso: "José, <comando>". Sem IA: só palavras conhecidas, para andar não depender de modelo grande.
"""

import difflib
import json
import os
import re
import unicodedata
from typing import NamedTuple, Optional

CAMINHO_DICIONARIO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "comandos_voz.json")

MAX_APOS_JOSE = 5  # quantas palavras depois do "José" ainda contam ("José, vai pra frente")
CORTE_FUZZY = 0.8  # semelhança mínima para aceitar uma variação não listada (só palavras com 5+ letras)
CORTE_FUZZY_JOSE = 0.75  # "jome", "jone", "joze"
MIN_LETRAS_FUZZY = 5


class Interpretacao(NamedTuple):
    chamou: bool = False  # o José foi chamado na frase
    comando: Optional[str] = None  # id do comando ("frente", "parar") ou do pedido ("conversa", "historia")
    tipo: Optional[str] = None  # "comando" (vai para o robô) ou "pedido" (o José mesmo atende)
    sem_chamar: bool = False  # tinha palavra de comando, mas faltou o "José"


def normalizar(texto: str) -> str:
    """Minúsculo, sem acento nem pontuação."""
    texto = unicodedata.normalize("NFKD", texto.lower().replace("[unk]", " unk "))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", texto)


def tokens(texto: str) -> list:
    return normalizar(texto).split()


class Dicionario:
    def __init__(self, dados: dict):
        self.dados = dados
        self.chamar = {normalizar(p) for p in dados["chamar"]}
        self.ignorar = {normalizar(p) for p in dados["ignorar"]}
        self.palavras = {}  # palavra normalizada -> (tipo, id)
        for tipo, chave in (("comando", "comandos"), ("pedido", "pedidos")):
            for id_, item in dados[chave].items():
                for palavra in item["palavras"]:
                    self.palavras[normalizar(palavra)] = (tipo, id_)
        self.ambiguas = {normalizar(p) for p in dados["comandos"]["parar"].get("_ambiguas", [])}
        self.rotulos = {id_: item["rotulo"] for chave in ("comandos", "pedidos") for id_, item in dados[chave].items()}

    def buscar(self, token: str):
        """(tipo, id) da palavra, ou None. Aceita variações parecidas com uma palavra do dicionário."""
        if token in self.ignorar or token in self.chamar:
            return None
        achado = self.palavras.get(token)
        if achado or len(token) < MIN_LETRAS_FUZZY:
            return achado
        parecida = difflib.get_close_matches(token, [p for p in self.palavras if len(p) >= MIN_LETRAS_FUZZY], n=1, cutoff=CORTE_FUZZY)
        return self.palavras[parecida[0]] if parecida else None

    def e_chamar(self, token: str) -> bool:
        if token in self.chamar:
            return True
        return len(token) >= 4 and difflib.SequenceMatcher(None, token, "jose").ratio() >= CORTE_FUZZY_JOSE

    def gramatica(self) -> list:
        """Palavras para o Vosk (lista fechada): o dicionário todo, mais as palavras de apoio."""
        palavras = list(self.dados["chamar"]) + list(self.dados["ignorar"]) + list(self.dados["gramatica_extra"])
        for chave in ("comandos", "pedidos"):
            for item in self.dados[chave].values():
                palavras += item["palavras"]
        unicas = dict.fromkeys(p.lower() for p in palavras if p != "unk")
        return list(unicas) + ["[unk]"]


def carregar(caminho: str = CAMINHO_DICIONARIO) -> Dicionario:
    with open(caminho, encoding="utf-8") as f:
        return Dicionario(json.load(f))


DICIONARIO = carregar()


def _primeiro_comando(palavras: list, dic: Dicionario):
    """Primeira palavra de comando/pedido da lista; "para" só conta como parar se nada mais vem depois."""
    achados = [(i, dic.buscar(p), p) for i, p in enumerate(palavras)]
    achados = [(i, a, p) for i, a, p in achados if a]
    for n, (i, (tipo, id_), palavra) in enumerate(achados):
        resto_tem_comando = any(a[1] != "parar" for _, a, _ in achados[n + 1:])
        if id_ == "parar" and palavra in dic.ambiguas and resto_tem_comando:
            continue  # "vai para frente": o "para" é preposição
        return tipo, id_
    return None


def interpretar(texto: str, chamado: bool = False, dic: Dicionario = DICIONARIO) -> Interpretacao:
    """O que a frase pede.

    chamado=True quando o José já foi chamado antes (ele está "ouvindo"): a palavra de comando já basta.
    Sem isso, o comando só vale depois de "José" na mesma frase; "pare"/"para" valem sozinhos.
    """
    palavras = tokens(texto)
    for i, palavra in enumerate(palavras):
        if dic.e_chamar(palavra):
            achado = _primeiro_comando(palavras[i + 1:i + 1 + MAX_APOS_JOSE], dic)
            return Interpretacao(True, achado[1], achado[0]) if achado else Interpretacao(True)
    if chamado:
        achado = _primeiro_comando(palavras, dic)
        return Interpretacao(False, achado[1], achado[0]) if achado else Interpretacao()
    # Sem "José": só um "pare"/"para" dito sozinho. Frases comuns com "para" não podem parar o robô
    if len(palavras) == 1 and dic.buscar(palavras[0]) == ("comando", "parar"):
        return Interpretacao(False, "parar", "comando")
    return Interpretacao(sem_chamar=any(dic.buscar(p) for p in palavras))
