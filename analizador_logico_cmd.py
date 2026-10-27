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



# ---------------------------------------------------------------------------
# Interfaz de escritorio: Tkinter (incluido en Python)
# ---------------------------------------------------------------------------
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path

FONDO = '#F2F7F4'
OSCURO = '#103C31'
VERDE = '#167453'
CLARO = '#DDF2E6'
TEXTO = '#183B32'
GRIS = '#647D72'
ROJO = '#AE4141'
ARCHIVO = Path.home() / '.logicflow_base.json'
EJEMPLO = ('Si es de día, entonces voy a trabajar\n'
           'Si llueve, entonces no voy a trabajar\nEs de día')


class Aplicacion(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('LogicFlow | Motor de inferencia y tableaux semánticos')
        self.geometry('1180x690')
        self.minsize(820, 480)
        self.configure(bg=FONDO)
        self.sistema = LogicFlow()
        self.raiz = None
        self.terminales = []
        self._estilos()
        self._interfaz()
        self._cargar()
        self._actualizar_tablas()
        self.protocol('WM_DELETE_WINDOW', self._cerrar)

    def _estilos(self):
        est = ttk.Style(self)
        if 'clam' in est.theme_names():
            est.theme_use('clam')
        est.configure('Panel.TFrame', background='white')
        est.configure('Main.TFrame', background=FONDO)
        est.configure('Grid.Treeview', font=('Segoe UI', 10), rowheight=29,
                      background='white', foreground=TEXTO, fieldbackground='white', borderwidth=0)
        est.configure('Grid.Treeview.Heading', font=('Segoe UI', 10, 'bold'),
                      background=CLARO, foreground=OSCURO, padding=7)
        est.map('Grid.Treeview', background=[('selected', '#B8E7CF')], foreground=[('selected', OSCURO)])
        est.configure('Modern.TNotebook', background=FONDO, borderwidth=0)
        est.configure('Modern.TNotebook.Tab', padding=(17, 10), font=('Segoe UI', 10, 'bold'))
        est.map('Modern.TNotebook.Tab', background=[('selected', 'white')], foreground=[('selected', VERDE)])

    def _boton(self, padre, nombre, accion, principal=False):
        return tk.Button(padre, text=nombre, command=accion,
                         bg=VERDE if principal else CLARO, fg='white' if principal else OSCURO,
                         activebackground=OSCURO if principal else '#C8EAD7',
                         activeforeground='white' if principal else OSCURO,
                         relief='flat', bd=0, padx=15, pady=10, cursor='hand2',
                         font=('Segoe UI', 10, 'bold'))

    def _interfaz(self):
        cab = tk.Frame(self, bg=OSCURO, padx=26, pady=18)
        cab.pack(fill='x')
        tk.Label(cab, text='◈  LOGICFLOW', fg='white', bg=OSCURO,
                 font=('Segoe UI', 23, 'bold')).pack(anchor='w')
        tk.Label(cab, text='Motor de inferencia  /  Tableaux semánticos  /  Sistemas Expertos',
                 fg='#ACDAC6', bg=OSCURO, font=('Segoe UI', 10)).pack(anchor='w', pady=(2, 0))
        centro = tk.PanedWindow(self, orient='horizontal', bg=FONDO, sashwidth=8,
                                bd=0, relief='flat')
        centro.pack(fill='both', expand=True, padx=18, pady=(16, 7))
        iz = tk.Frame(centro, bg='white', padx=18, pady=16)
        de = tk.Frame(centro, bg='white', padx=14, pady=12)
        centro.add(iz, minsize=320, width=405)
        centro.add(de, minsize=480)
        tk.Label(iz, text='BASE DE CONOCIMIENTO', bg='white', fg=OSCURO,
                 font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        tk.Label(iz, text='Escribe un hecho o una regla por línea.', bg='white', fg=GRIS,
                 font=('Segoe UI', 10)).pack(anchor='w', pady=(4, 12))
        self.entrada = tk.Text(iz, height=7, wrap='word', bg='#F7FAF8', fg=TEXTO,
                               font=('Segoe UI', 11), bd=1, relief='solid',
                               highlightthickness=1, highlightbackground='#D4E8DD',
                               insertbackground=VERDE, padx=11, pady=11)
        self.entrada.pack(fill='x')
        self.entrada.insert('1.0', 'Si es de día, entonces voy a trabajar\nSi llueve, entonces no voy a trabajar\nEs de día')
        fila = tk.Frame(iz, bg='white')
        fila.pack(fill='x', pady=(12, 8))
        self._boton(fila, '+ Agregar reglas', self.agregar, True).pack(side='left', padx=(0, 7))
        self._boton(fila, 'Ejemplo', self.ejemplo).pack(side='left')
        tk.Frame(iz, bg='#E0EBE5', height=1).pack(fill='x', pady=13)
        tk.Label(iz, text='ÁTOMOS IDENTIFICADOS', bg='white', fg=OSCURO,
                 font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(0, 8))
        self.tv_atomos = ttk.Treeview(iz, columns=('letra', 'significado'), show='headings',
                                     height=5, style='Grid.Treeview')
        self.tv_atomos.heading('letra', text='Letra')
        self.tv_atomos.heading('significado', text='Significado')
        self.tv_atomos.column('letra', width=60, stretch=False, anchor='center')
        self.tv_atomos.column('significado', width=255)
        self.tv_atomos.pack(fill='x')
        tk.Label(iz, text='REGLAS Y FÓRMULAS', bg='white', fg=OSCURO,
                 font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(14, 7))
        self.tv_reglas = ttk.Treeview(iz, columns=('n', 'f'), show='headings',
                                     height=7, style='Grid.Treeview')
        self.tv_reglas.heading('n', text='Regla')
        self.tv_reglas.heading('f', text='Fórmula lógica')
        self.tv_reglas.column('n', width=63, stretch=False, anchor='center')
        self.tv_reglas.column('f', width=252)
        self.tv_reglas.pack(fill='both', expand=True)
        fila2 = tk.Frame(iz, bg='white')
        fila2.pack(fill='x', pady=(12, 0))
        self._boton(fila2, 'Analizar árbol', self.analizar_gui, True).pack(side='left', padx=(0, 7))
        self._boton(fila2, 'Borrar todo', self.borrar).pack(side='left')
        self.estado = tk.StringVar(value='Listo para agregar reglas.')
        tk.Label(iz, textvariable=self.estado, bg='white', fg=GRIS, wraplength=340,
                 justify='left', font=('Segoe UI', 9)).pack(anchor='w', pady=(12, 0))

        pestanas = ttk.Notebook(de, style='Modern.TNotebook')
        pestanas.pack(fill='both', expand=True)
        ar = tk.Frame(pestanas, bg='white')
        res = tk.Frame(pestanas, bg='white')
        pestanas.add(ar, text='Árbol semántico')
        pestanas.add(res, text='Modelos y resultados')
        barra = tk.Frame(ar, bg='white')
        barra.pack(fill='x', pady=(5, 8))
        tk.Label(barra, text='TABLEAU SEMÁNTICO', fg=OSCURO, bg='white',
                 font=('Segoe UI', 12, 'bold')).pack(side='left')
        self._boton(barra, 'Ajustar vista', self._centrar).pack(side='right')
        holder = tk.Frame(ar, bg='#F8FBF9')
        holder.pack(fill='both', expand=True)
        self.lienzo = tk.Canvas(holder, bg='#F8FBF9', highlightthickness=0)
        self.scroll_y = ttk.Scrollbar(holder, orient='vertical', command=self.lienzo.yview)
        self.scroll_x = ttk.Scrollbar(holder, orient='horizontal', command=self.lienzo.xview)
        self.lienzo.configure(yscrollcommand=self.scroll_y.set, xscrollcommand=self.scroll_x.set)
        self.scroll_y.pack(side='right', fill='y')
        self.scroll_x.pack(side='bottom', fill='x')
        self.lienzo.pack(fill='both', expand=True)
        self.lienzo.create_text(340, 160, text='Agrega reglas y pulsa «Analizar árbol»',
                                fill=GRIS, font=('Segoe UI', 14))
        self.resultado = tk.Text(res, bg='white', fg=TEXTO, wrap='word', bd=0,
                                  font=('Consolas', 11), padx=16, pady=16, state='disabled')
        self.resultado.pack(fill='both', expand=True)
        pie = tk.Frame(self, bg=FONDO, padx=20, pady=7)
        pie.pack(fill='x')
        tk.Label(pie, text='Los datos se guardan automáticamente en tu computadora.', bg=FONDO,
                 fg=GRIS, font=('Segoe UI', 9)).pack(side='left')
        tk.Label(pie, text='∧   ∨   ¬   →   ↔', bg=FONDO, fg=VERDE,
                 font=('Segoe UI', 12, 'bold')).pack(side='right')

    def _guardar(self):
        try:
            ARCHIVO.write_text(json.dumps([s for s, _ in self.sistema.reglas],
                                          ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError as error:
            self.estado.set('No se pudo guardar: ' + str(error))

    def _cargar(self):
        if ARCHIVO.exists():
            try:
                entradas = json.loads(ARCHIVO.read_text(encoding='utf-8'))
                for s in entradas:
                    if isinstance(s, str):
                        self.sistema.agregar(s)
            except (OSError, ValueError, TypeError):
                self.estado.set('No fue posible cargar la base anterior.')

    def _actualizar_tablas(self):
        for t in (self.tv_atomos, self.tv_reglas):
            for x in t.get_children():
                t.delete(x)
        for simbolo, significado in self.sistema.atomos.values():
            self.tv_atomos.insert('', 'end', values=(simbolo, significado))
        for i, (_, formula) in enumerate(self.sistema.reglas, 1):
            self.tv_reglas.insert('', 'end', values=(f'R{i}', fmt(formula)))

    def agregar(self):
        lineas = [x.strip() for x in re.split('[\n;]+', self.entrada.get('1.0', 'end')) if x.strip()]
        if not lineas:
            messagebox.showinfo('Sin reglas', 'Escribe al menos un hecho o regla.')
            return
        errores = []
        for linea in lineas:
            try:
                self.sistema.agregar(linea)
            except ValueError as error:
                errores.append(f'{linea}: {error}')
        self._guardar()
        self._actualizar_tablas()
        self.estado.set(f'{len(lineas)-len(errores)} reglas agregadas · {len(self.sistema.reglas)} en total.')
        if errores:
            messagebox.showwarning('Algunas reglas no se agregaron', '\n'.join(errores[:8]))
        else:
            self.entrada.delete('1.0', 'end')

    def ejemplo(self):
        self.entrada.delete('1.0', 'end')
        self.entrada.insert('1.0', EJEMPLO)
        self.estado.set('Ejemplo listo: pulsa «Agregar reglas».')

    def borrar(self):
        if not messagebox.askyesno('Confirmar', '¿Borrar todas las reglas guardadas y sus átomos?'):
            return
        self.sistema = LogicFlow()
        self.raiz = None
        self.terminales = []
        self._guardar()
        self._actualizar_tablas()
        self.lienzo.delete('all')
        self._poner_resultado('Base vacía. Agrega reglas para comenzar.')
        self.estado.set('Base de conocimiento eliminada.')

    def _poner_resultado(self, texto):
        self.resultado.configure(state='normal')
        self.resultado.delete('1.0', 'end')
        self.resultado.insert('1.0', texto)
        self.resultado.configure(state='disabled')

    def analizar_gui(self):
        if not self.sistema.reglas:
            messagebox.showinfo('Base vacía', 'Agrega al menos una regla o hecho.')
            return
        try:
            self.raiz, self.terminales = tableau([f for _, f in self.sistema.reglas])
        except (ValueError, RuntimeError, RecursionError) as error:
            messagebox.showerror('No se pudo analizar', str(error))
            return
        abiertas = [r for r in self.terminales if r.cierre.startswith('✓')]
        cerradas = [r for r in self.terminales if r.cierre.startswith('✕')]
        lineas = [f'BASE: {"SATISFACIBLE" if abiertas else "INSATISFACIBLE"}',
                  '', f'Ramas abiertas: {len(abiertas)}', f'Ramas cerradas: {len(cerradas)}', '']
        simbolos = [s for s, _ in self.sistema.atomos.values()]
        for i, rama in enumerate(abiertas, 1):
            v = {}
            for f in rama.formulas:
                if f.op == 'atom':
                    v[f.a] = 'V'
                elif f.op == '¬' and f.a.op == 'atom':
                    v[f.a.a] = 'F'
            lineas.append(f'RAMA ABIERTA {i} (nodo {rama.numero})')
            lineas.append('   ' + ', '.join(f'{s} = {v.get(s, "libre")}' for s in simbolos))
            lineas.append('')
        if not abiertas:
            lineas.append('No existe asignación que satisfaga todas las reglas.')
        else:
            lineas.append('«Libre» significa que puede valer V o F.')
        lineas.extend(['', 'FÓRMULAS INICIALES:'])
        lineas.extend(f'R{i}: {fmt(f)}' for i, (_, f) in enumerate(self.sistema.reglas, 1))
        self._poner_resultado('\n'.join(lineas))
        self._dibujar_arbol()
        self.estado.set(f'Análisis completo: {len(abiertas)} abiertas, {len(cerradas)} cerradas.')

    def _dibujar_arbol(self):
        self.lienzo.delete('all')
        raiz = self.raiz
        if raiz is None:
            return
        # Asignar una columna a cada hoja; centros intermedios = promedio de hijos.
        posiciones = {}
        indice = [0]
        def asignar(r, profundidad=0):
            if not r.hijos:
                x = indice[0] * 260 + 150
                indice[0] += 1
            else:
                xs = [asignar(h, profundidad + 1) for h in r.hijos]
                x = sum(xs) / len(xs)
            posiciones[id(r)] = (x, profundidad * 160 + 90)
            return x
        asignar(raiz)
        def dibujar(r):
            x, y = posiciones[id(r)]
            for hijo in r.hijos:
                hx, hy = posiciones[id(hijo)]
                self.lienzo.create_line(x, y+47, hx, hy-47, fill='#88B5A0', width=2)
                dibujar(hijo)
            if r.cierre.startswith('✕'):
                relleno, borde, estado = '#FFF0ED', '#C96D65', '✕ CERRADA'
            elif r.cierre.startswith('✓'):
                relleno, borde, estado = '#E2F5E8', '#49A772', '✓ ABIERTA'
            else:
                relleno, borde, estado = 'white', '#9BC6B0', 'EXPANSIÓN'
            w, h = 232, 100
            self.lienzo.create_rectangle(x-w/2, y-h/2, x+w/2, y+h/2,
                                         fill=relleno, outline=borde, width=2)
            self.lienzo.create_text(x, y-34, text=f'NODO {r.numero}    {estado}',
                                    font=('Segoe UI', 10, 'bold'), fill=OSCURO)
            actuales = [fmt(f) + (' ✓' if i in r.procesadas else '')
                        for i, f in enumerate(r.formulas)]
            texto = ' ; '.join(actuales)
            if len(texto) > 110:
                texto = texto[:107] + '…'
            self.lienzo.create_text(x, y, text=texto, width=207,
                                    font=('Segoe UI', 9), fill=TEXTO, justify='center')
            if r.cierre.startswith('✕'):
                nota = r.cierre[2:]
            else:
                nota = r.paso.replace(' | ', ' · ')
            if len(nota) > 55:
                nota = nota[:52] + '…'
            self.lienzo.create_text(x, y+37, text=nota, width=210,
                                    font=('Segoe UI', 8), fill=ROJO if r.cierre.startswith('✕') else GRIS)
        dibujar(raiz)
        ancho = max(680, indice[0] * 260 + 40)
        alto = max(y for x, y in posiciones.values()) + 110
        self.lienzo.configure(scrollregion=(0, 0, ancho, alto))
        self._centrar()

    def _centrar(self):
        self.lienzo.xview_moveto(0)
        self.lienzo.yview_moveto(0)

    def _cerrar(self):
        self._guardar()
        self.destroy()


if __name__ == '__main__':
    Aplicacion().mainloop()
