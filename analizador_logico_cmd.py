import re
import unicodedata

class LogicFlow:
    def __init__(self):
        self.variables = {}
        self.reglas = []

    def normalizar(self, texto):
        texto = unicodedata.normalize("NFD", texto.lower())
        return "".join(c for c in texto if unicodedata.category(c) != "Mn").strip(" .,!?")

    def obtener_letra(self, texto):
        clave = self.normalizar(texto)
        if clave not in self.variables:
            n = len(self.variables)
            letra = chr(65 + n) if n < 26 else f"P{n+1}"
            self.variables[clave] = (letra, texto.strip())
        return self.variables[clave][0]

    def convertir(self, texto):
        texto = texto.strip(" .,!?")
        partes = re.split(r"\s+(y|o|pero)\s+", texto, flags=re.I)
        if not texto or re.search(r"\b(y|o|pero)$", texto, re.I):
            raise ValueError("Proposicion incompleta")

        salida = []
        for parte in partes:
            clave = self.normalizar(parte)
            if clave in ("y", "pero"):
                salida.append("∧")
            elif clave == "o":
                salida.append("∨")
            elif clave:
                salida.append(self.obtener_letra(parte))
            else:
                raise ValueError("Proposicion vacia")

        expresion = " ".join(salida)
        return f"({expresion})" if len(salida) > 1 else expresion

    def agregar(self, texto):
        partes = re.fullmatch(
            r"si\s+(.+?)\s*(?:,\s*entonces\s+|\s+entonces\s+|,\s*)(.+)",
            texto.strip(" .!?"), re.I
        )
        if not partes:
            raise ValueError("Usa: Si condicion, entonces resultado")

        a = self.convertir(partes.group(1))
        b = self.convertir(partes.group(2))
        regla = f"{a} → {b}"
        self.reglas.append(regla)
        print("\n[OK] Regla creada:", regla)

    def mostrar(self):
        print("\n--- VARIABLES ---")
        for letra, texto in self.variables.values():
            print(f"{letra} = {texto}")
        print("\n--- REGLAS ---")
        for i, regla in enumerate(self.reglas, 1):
            print(f"LF-{i}: {regla}")

def iniciar():
    sistema = LogicFlow()

    while True:
        print("\n====== LOGICFLOW ======")
        print("1. Agregar regla")
        print("2. Ver variables y reglas")
        print("3. Ayuda")
        print("4. Salir")

        opcion = input("Opcion: ").strip()

        if opcion == "1":
            try:
                sistema.agregar(input("Escribe la regla: "))
            except ValueError as e:
                print("[ERROR]", e)
        elif opcion == "2":
            sistema.mostrar()
        elif opcion == "3":
            print("Ejemplo: Si estudio y hago tarea, entonces apruebo.")
            print("Operadores: y = ∧, o = ∨, pero = ∧")
        elif opcion == "4":
            print("Programa finalizado.")
            break
        else:
            print("Opcion incorrecta.")

if __name__ == "__main__":
    iniciar()
