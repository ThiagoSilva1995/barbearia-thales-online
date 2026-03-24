# Formatadores
import re

def formatar_telefone(tel):
    return re.sub(r'\D', '', tel)

