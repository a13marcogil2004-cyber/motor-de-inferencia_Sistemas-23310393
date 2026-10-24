import re
import unicodedata
from dataclasses import dataclass, field


def normalizar(s):
    s = unicodedata.normalize('NFD', s.casefold())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', s).strip(' .,;:¡!¿?')


@dataclass(frozen=True)
class F:
    op: str
    a: object
    b: object = None


def neg(f):
    return F('¬', f)


def literal(f):
    return f.op == 'atom' or (f.op == '¬' and f.a.op == 'atom')


def fmt(f):
    if f.op == 'atom':
        return f.a
    if f.op == '¬':
        s = fmt(f.a)
        return '¬' + (s if f.a.op in ('atom', '¬') else '(' + s + ')')
    return '(' + fmt(f.a) + ' ' + f.op + ' ' + fmt(f.b) + ')'


class LogicFlow:
    def __init__(self):
        self.atomos = {}
        self.reglas = []

    def letra(self, frase):
        clave = normalizar(frase)
        if not clave:
            raise ValueError('Falta una proposición.')
        if clave not in self.atomos:
            n = len(self.atomos)
            # p, q, r, s... y luego p1, q1...
            base = 'pqrstuvwxyzabcdefghijklmno'
            simbolo = base[n % len(base)] + (str(n // len(base) + 1) if n >= len(base) else '')
            self.atomos[clave] = (simbolo, frase.strip())
        return F('atom', self.atomos[clave][0])

    def interpretar(self, texto):
        texto = texto.strip().strip(' .;!?¡¿')
        if not texto:
            raise ValueError('Escribe una proposición o regla.')
        # Los condicionales completos se identifican antes de dividir conectivos.
        cond = re.fullmatch(r'si\s+(.+?)(?:\s*,\s*entonces\s+|\s+entonces\s+|\s*,\s*)(.+)', texto, re.I)
        if cond:
            return F('→', self.interpretar(cond.group(1)), self.interpretar(cond.group(2)))
        # Bicondicional en español, incluso entre dos frases.
        p = re.split(r'\s+si\s+y\s+solo\s+si\s+', texto, maxsplit=1, flags=re.I)
        if len(p) == 2:
            return F('↔', self.interpretar(p[0]), self.interpretar(p[1]))
        # Expresiones de conjunción y disyunción (∧ tiene mayor prioridad).
        partes = re.split(r'\s+(o)\s+', texto, flags=re.I)
        if len(partes) > 1:
            if any(not x.strip() for x in partes[::2]):
                raise ValueError('Disyunción incompleta.')
            nodo = self.interpretar(partes[0])
            for i in range(2, len(partes), 2):
                nodo = F('∨', nodo, self.interpretar(partes[i]))
            return nodo
        partes = re.split(r'\s+(y|pero)\s+', texto, flags=re.I)
        if len(partes) > 1:
            if any(not x.strip() for x in partes[::2]):
                raise ValueError('Conjunción incompleta.')
            nodo = self.interpretar(partes[0])
            for i in range(2, len(partes), 2):
                nodo = F('∧', nodo, self.interpretar(partes[i]))
            return nodo
        m = re.fullmatch(r'no\s+(.+)', texto, re.I)
        if m:
            return neg(self.interpretar(m.group(1)))
        if normalizar(texto) in ('no', 'si', 'entonces', 'y', 'o', 'pero'):
            raise ValueError('La regla está incompleta.')
        return self.letra(texto)

    def agregar(self, texto):
        f = self.interpretar(texto)
        self.reglas.append((texto.strip(), f))
        return f

    def agregar_varias(self, texto):
        entradas = [s.strip() for s in re.split(r'[\n;]+', texto) if s.strip()]
        total = 0
        for entrada in entradas:
            try:
                f = self.agregar(entrada)
                print(f'  R{len(self.reglas)}: {fmt(f)}')
                total += 1
            except ValueError as e:
                print(f'  [ERROR] {entrada}: {e}')
        return total

    def mostrar(self):
        print('\n=== TABLA DE ÁTOMOS ===')
        if not self.atomos:
            print('  (vacía)')
        for letra, frase in self.atomos.values():
            print(f'  {letra} = {frase}')
        print('\n=== BASE DE CONOCIMIENTO ===')
        for i, (original, f) in enumerate(self.reglas, 1):
            print(f'  R{i}: {original}\n       {fmt(f)}')
        if not self.reglas:
            print('  (vacía)')


@dataclass
class Rama:
    formulas: list
    procesadas: set = field(default_factory=set)
    paso: str = ''
    hijos: list = field(default_factory=list)
    cierre: str = ''
    numero: int = 0


def expansion(f):
    """Devuelve (tipo, alternativas); cada alternativa agrega una lista de fórmulas."""
    op = f.op
    if op == '¬':
        g = f.a
        if g.op == '¬':
            return 'α: ¬¬', [[g.a]]
        if g.op == '∨':
            return 'α: ¬∨', [[neg(g.a), neg(g.b)]]
        if g.op == '→':
            return 'α: ¬→', [[g.a, neg(g.b)]]
        if g.op == '∧':
            return 'β: ¬∧', [[neg(g.a)], [neg(g.b)]]
        if g.op == '↔':
            return 'β: ¬↔', [[g.a, neg(g.b)], [neg(g.a), g.b]]
    if op == '∧':
        return 'α: ∧', [[f.a, f.b]]
    if op == '∨':
        return 'β: ∨', [[f.a], [f.b]]
    if op == '→':
        return 'β: →', [[neg(f.a)], [f.b]]
    if op == '↔':
        return 'β: ↔', [[f.a, f.b], [neg(f.a), neg(f.b)]]
    return None


def contradiccion(formulas):
    positivos = {f.a for f in formulas if f.op == 'atom'}
    negativos = {f.a.a for f in formulas if f.op == '¬' and f.a.op == 'atom'}
    comun = sorted(positivos & negativos)
    return comun[0] if comun else ''


def tableau(formulas, max_nodos=3000):
    raiz = Rama(list(dict.fromkeys(formulas)), paso='Todas las reglas verdaderas')
    terminales = []
    contador = [0]

    def crecer(rama):
        contador[0] += 1
        rama.numero = contador[0]
        if contador[0] > max_nodos:
            raise RuntimeError('El árbol excedió el límite de seguridad de nodos.')
        contra = contradiccion(rama.formulas)
        if contra:
            rama.cierre = f'✕ contradicción: {contra} y ¬{contra}'
            terminales.append(rama)
            return
        pendientes = [(i, f) for i, f in enumerate(rama.formulas)
                      if i not in rama.procesadas and not literal(f)]
        if not pendientes:
            rama.cierre = '✓ ABIERTA'
            terminales.append(rama)
            return
        # Preferir α antes que β ayuda a minimizar ramificaciones.
        candidatos = [(i, f, expansion(f)) for i, f in pendientes]
        i, f, (tipo, opciones) = next((c for c in candidatos if c[2][0].startswith('α')), candidatos[0])
        rama.paso += (' | ' if rama.paso else '') + f'Aplicar {fmt(f)} [{tipo}] ✓'
        for valores in opciones:
            nuevas = rama.formulas[:]
            for v in valores:
                if v not in nuevas:
                    nuevas.append(v)
            hijo = Rama(nuevas, rama.procesadas | {i}, paso='Añadir: ' + ', '.join(fmt(x) for x in valores))
            rama.hijos.append(hijo)
            crecer(hijo)
    crecer(raiz)
    return raiz, terminales


def dibujar(rama, prefijo='', ultimo=True, raiz=True):
    signo = '' if raiz else ('└── ' if ultimo else '├── ')
    nuevas = ' | '.join(fmt(f) + (' ✓' if i in rama.procesadas else '')
                       for i, f in enumerate(rama.formulas))
    print(prefijo + signo + f'[{rama.numero}] {rama.paso}')
    pref = prefijo + ('' if raiz else ('    ' if ultimo else '│   '))
    print(pref + '     ' + nuevas)
    if rama.cierre:
        print(pref + '     ' + rama.cierre)
    for i, hijo in enumerate(rama.hijos):
        dibujar(hijo, pref, i == len(rama.hijos) - 1, False)


def analizar(sistema):
    if not sistema.reglas:
        print('Primero agrega reglas o hechos.')
        return
    raiz, terminales = tableau([f for _, f in sistema.reglas])
    print('\n=== TABLEAU SEMÁNTICO ===')
    dibujar(raiz)
    abiertas = [r for r in terminales if r.cierre.startswith('✓')]
    cerradas = [r for r in terminales if r.cierre.startswith('✕')]
    print(f'\nResultado: {len(cerradas)} rama(s) cerrada(s), {len(abiertas)} abierta(s).')
    if not abiertas:
        print('BASE INSATISFACIBLE: no existe asignación que cumpla todas las reglas.')
        return
    print('BASE SATISFACIBLE: modelos de las ramas abiertas (— = valor libre):')
    todas = [par[0] for par in sistema.atomos.values()]
    for i, r in enumerate(abiertas, 1):
        vals = {}
        for f in r.formulas:
            if f.op == 'atom':
                vals[f.a] = 'V'
            elif f.op == '¬' and f.a.op == 'atom':
                vals[f.a.a] = 'F'
        print(f'  Rama {i} [nodo {r.numero}]: ' + ', '.join(f'{k} = {vals.get(k, "—")}' for k in todas))
    print('Las variables libres pueden tomar V o F; las asignaciones mostradas satisfacen la base.')


def iniciar():
    s = LogicFlow()
    while True:
        print('\n' + '=' * 45)
        print('       LOGICFLOW | SISTEMAS EXPERTOS')
        print('=' * 45)
        print('1. Agregar una regla o hecho')
        print('2. Agregar varias reglas (una por línea)')
        print('3. Ver átomos y base de conocimiento')
        print('4. Construir y resolver tableau')
        print('5. Cargar ejemplo de evaluación')
        print('6. Borrar base de conocimiento')
        print('7. Ayuda')
        print('0. Salir')
        try:
            op = input('Opción: ').strip()
            if op == '1':
                f = s.agregar(input('Regla o hecho: '))
                print(f'[OK] R{len(s.reglas)}: {fmt(f)}')
            elif op == '2':
                print('Escribe las reglas; deja una línea vacía para terminar:')
                entradas = []
                while True:
                    linea = input('> ')
                    if not linea.strip():
                        break
                    entradas.append(linea)
                print(f'Agregadas: {s.agregar_varias(chr(10).join(entradas))}')
            elif op == '3':
                s.mostrar()
            elif op == '4':
                s.mostrar()
                analizar(s)
            elif op == '5':
                s = LogicFlow()
                s.agregar_varias('Si es de día, entonces voy a trabajar\nSi llueve, entonces no voy a trabajar\nEs de día')
                s.mostrar()
                analizar(s)
            elif op == '6':
                s = LogicFlow()
                print('Base eliminada.')
            elif op == '7':
                print('Admite hechos, no, y, o, pero, si... entonces, y si y solo si.')
                print('Ejemplo: Si es de día, entonces voy a trabajar')
                print('Una regla por línea; ∧ precede a ∨. Usa expresiones sencillas.')
            elif op == '0':
                print('Hasta luego.')
                break
            else:
                print('Opción no válida.')
        except (ValueError, RuntimeError) as e:
            print('[ERROR]', e)
        except (EOFError, KeyboardInterrupt):
            print('\nFin.')
            break


if __name__ == '__main__':
    iniciar()
