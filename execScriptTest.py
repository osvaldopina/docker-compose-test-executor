

def main(**params):
    soma = 0
    if 'a' in params:
        soma += params['a']
    if 'b' in params:
        soma += params['b']
    if 'c' in params:
        soma += params['c']
    return soma
