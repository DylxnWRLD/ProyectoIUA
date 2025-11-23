import os
import speech_recognition as sr
import pyttsx3
import whisper
import threading
import time
import queue # <--- IMPORTANTE: Necesario para la comunicación entre hilos
from datetime import datetime
import warnings
import torch
from groq import Groq

# Ignorar advertencias
warnings.filterwarnings("ignore")

# ========================
# 1. CONFIGURACIÓN DE LA NUBE (GROQ)
# ========================
API_KEY = "" 

try:
    client = Groq(api_key=API_KEY)
    print("☁️ Conexión a Nube (Groq) lista.")
except Exception as e:
    print(f"❌ Error conectando a Groq: {e}")
    exit()

# ========================
# 2. CONFIGURACIÓN DEL OÍDO (WHISPER LOCAL)
# ========================
print("🔄 Cargando Oído (Whisper Small)...")

try:
    torch.set_num_threads(6) 
except:
    pass

try:
    whisper_model = whisper.load_model("small")
    print("✅ Whisper listo. Sistema de voz activado.")
except Exception as e:
    print(f"Error cargando Whisper: {e}")
    exit()

r = sr.Recognizer()
r.pause_threshold = 1.0
r.energy_threshold = 400
r.dynamic_energy_threshold = True

os.makedirs("notas", exist_ok=True)

# ========================
# 3. FUNCIONES DE MOTOR (AUDIO Y VOZ)
# ========================

def reproducir_sonido(tipo="inicio"):
    try:
        import winsound
        freq = 1000 if tipo == "inicio" else 500
        winsound.Beep(freq, 200)
    except:
        pass

def hablar(texto):
    print(f"🤖: {texto}")
    try:
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        for voice in voices:
            if "spanish" in voice.name.lower() or "es-es" in voice.id.lower():
                engine.setProperty('voice', voice.id)
                break
        engine.setProperty('rate', 160)
        engine.say(texto)
        engine.runAndWait()
        del engine
    except:
        pass

def escuchar_comando():
    """Escucha comandos cortos (Google)"""
    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source, duration=0.5)
        print("👂 Escuchando comando...")
        try:
            audio = r.listen(source, timeout=5, phrase_time_limit=5)
            texto = r.recognize_google(audio, language="es-ES").lower()
            print(f"🗣️ Comando: {texto}")
            return texto
        except:
            return ""

def escuchar_con_intentos(max_intentos=3, mensaje="Responde:"):
    for intento in range(max_intentos):
        if intento > 0:
            hablar(f"{mensaje}")
        texto = escuchar_comando()
        if texto: return texto
    return ""

# ========================
# 4. FUNCIONES DE GRABACIÓN PRO (MULTIHILO REAL)
# ========================

def grabar_y_transcribir_whisper():
    """
    SISTEMA MULTIHILO (PRODUCER-CONSUMER) MEJORADO:
    - Detecta más comandos de salida.
    - Filtra repeticiones (alucinaciones).
    """
    
    # Colas y banderas de control
    cola_audio = queue.Queue()
    evento_parar = threading.Event() 
    resultado_final = {"texto": ""}
    
    # --- CONFIGURACIÓN ANTI-FALLOS ---
    ALUCINACIONES = [
        "suscríbete", "subtítulos", "amara.org", "al canal", "dale like", 
        "gracias por ver", "copyright", "transcripción", "traducido por",
        "editado por"
    ]
    
    # Agregamos más variantes para que te entienda sí o sí
    PALABRAS_FIN = [
        "terminar nota", "finalizar nota", "guardar nota", 
        "fin de la nota", "fin de la grabación", "detener grabación",
        "hasta aquí", "cierra la nota", "basta de grabar",
        "ya es todo", "punto final", "Finalizó la nota"
    ]

    print("🤫 CALIBRANDO RUIDO...")
    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source, duration=1.0)
        r.energy_threshold = max(300, r.energy_threshold * 1.1)

    # ---------------------------------------------------------
    # HILO 1: EL OÍDO (Productor)
    # ---------------------------------------------------------
    def hilo_escucha():
        with sr.Microphone() as source:
            while not evento_parar.is_set():
                try:
                    # phrase_time_limit=8 para enviar paquetes más rápido
                    audio = r.listen(source, timeout=2, phrase_time_limit=8)
                    cola_audio.put(audio) 
                    print("🎤 ...", end="\r")
                except sr.WaitTimeoutError:
                    pass 
                except Exception as e:
                    if not evento_parar.is_set(): print(f"Error Oído: {e}")

    # ---------------------------------------------------------
    # HILO 2: EL CEREBRO (Consumidor)
    # ---------------------------------------------------------
    def hilo_procesamiento():
        nombre_temp = "temp_bloque.wav"
        ultimo_texto_procesado = "" # Variable para detectar bucles de repetición
        
        while not evento_parar.is_set() or not cola_audio.empty():
            try:
                audio_data = cola_audio.get(timeout=1) 
            except queue.Empty:
                continue

            try:
                with open(nombre_temp, "wb") as f:
                    f.write(audio_data.get_wav_data())

                contexto = resultado_final["texto"][-200:] if resultado_final["texto"] else "Español."
                
                res = whisper_model.transcribe(
                    nombre_temp, language="es", fp16=False, initial_prompt=contexto,
                    condition_on_previous_text=False, # Vital para evitar bucles
                    no_speech_threshold=0.6
                )
                texto = res["text"].strip()
                
                # --- FILTROS DE LIMPIEZA ---
                
                # 1. Si está vacío o es muy corto
                if not texto or len(texto) < 2: continue

                # 2. Filtro de Alucinaciones (YouTube)
                if any(aluc in texto.lower() for aluc in ALUCINACIONES):
                    continue

                # 3. FILTRO DE REPETICIÓN
                # Si el texto es igual al anterior, es una alucinación de Whisper. Lo ignoramos.
                if texto.lower() == ultimo_texto_procesado.lower():
                    continue
                ultimo_texto_procesado = texto # Actualizamos memoria

                print(f"➕ {texto}")

                # 4. DETECCIÓN DE FIN (Más flexible)
                texto_lower = texto.lower().replace(".", "").replace(",", "")
                encontrado_fin = False
                
                for cmd in PALABRAS_FIN:
                    if cmd in texto_lower:
                        idx = texto_lower.find(cmd)
                        parte_util = texto[:idx]
                        
                        if len(parte_util) > 2:
                            resultado_final["texto"] += " " + parte_util
                        
                        hablar("Oído, terminando...")
                        evento_parar.set() 
                        
                        with cola_audio.mutex: cola_audio.queue.clear()
                        return

                resultado_final["texto"] += " " + texto

            except Exception as e:
                print(f"Error Cerebro: {e}")
            finally:
                cola_audio.task_done()
        
        if os.path.exists(nombre_temp): os.remove(nombre_temp)

    # ---------------------------------------------------------
    # EJECUCIÓN
    # ---------------------------------------------------------
    hablar("Te escucho. Habla fluido. Di 'terminar nota' o 'listo' cuando quieras finalizar la nota.")
    threading.Thread(target=lambda: reproducir_sonido("inicio")).start()

    t_oido = threading.Thread(target=hilo_escucha)
    t_cerebro = threading.Thread(target=hilo_procesamiento)
    
    t_oido.start()
    t_cerebro.start()

    t_cerebro.join()
    evento_parar.set()
    t_oido.join()

    return resultado_final["texto"].strip()

# ========================
# 5. INTELIGENCIA ARTIFICIAL (GROQ)
# ========================

def generar_resumen_groq(texto):
    """Usa Groq (Llama 3) para resumir sin gastar CPU"""
    if len(texto.split()) < 5:
        return "Texto muy corto para resumir."

    prompt = f"""
    Actúa como un analista de texto experto. Analiza la siguiente transcripción:
    "{texto}"

    Tus instrucciones OBLIGATORIAS:
    1. Escribe un resumen conciso del tema principal.
    
    2. SOBRE LAS TAREAS (Lee con cuidado):
       - Solo extrae una lista de "TAREAS" si detectas una intención clara de acción futura real (ej: "recuérdame comprar pan", "tengo cita mañana").
       - IGNORA COMPLETAMENTE los ejemplos hipotéticos, metáforas o situaciones que se mencionan solo para explicar un tema (ej: "cuando uno tiene que entregar un trabajo...").
       - Si el texto es educativo, reflexivo o una historia, ASUME QUE NO HAY TAREAS.
       
    3. Formato de salida:
       - Resumen: [Tu resumen aquí]
       - TAREAS: [Lista de tareas] (SI NO HAY TAREAS REALES, OMITE ESTA SECCIÓN POR COMPLETO).
       
    4. Sin saludos ni charla extra.
    """
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.1
        )
        
        resultado = chat_completion.choices[0].message.content
        
        if "TAREAS" in resultado:
            partes = resultado.split("TAREAS")
            if len(partes) > 1:
                contenido_tareas = partes[1].strip().lower()
                palabras_vacias = ["nadie", "ninguna", "no hay", "n/a", "sin tareas"]
                if any(p in contenido_tareas for p in palabras_vacias) and len(contenido_tareas) < 50:
                    return partes[0].strip()
        
        return resultado

    except Exception as e:
        return f"Error en la nube: {e}"

# ========================
# 6. FUNCIONES DE GESTIÓN DE ARCHIVOS
# ========================

def contar_palabras(texto):
    return len(texto.split())

def convertir_texto_a_numero(texto):
    """Convierte palabras comunes de números a dígitos para la selección"""
    mapping = {
        "uno": 1, "una": 1, "primera": 1, "primero": 1, "1": 1,
        "dos": 2, "segunda": 2, "segundo": 2, "2": 2,
        "tres": 3, "tercera": 3, "tercero": 3, "3": 3,
        "cuatro": 4, "cuarta": 4, "4": 4,
        "cinco": 5, "quinta": 5, "5": 5
    }
    # Buscamos si alguna palabra del texto es un número
    for palabra in texto.split():
        palabra_limpia = palabra.replace(".", "").replace(",", "")
        if palabra_limpia in mapping:
            return mapping[palabra_limpia]
    return None

def pedir_nombre_archivo():
    hablar("¿Qué nombre le pongo al archivo?")
    nombre = escuchar_con_intentos(3, "Dime el nombre:")
    if not nombre:
        nombre = datetime.now().strftime("nota_%Y%m%d_%H%M%S")
        hablar(f"Usando nombre automático.")
    else:
        nombre = nombre.strip().replace(" ", "_")
    return nombre

def guardar_archivo(nombre, contenido):
    ruta = f"notas/{nombre}.txt"
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(contenido)
    hablar(f"Guardado como {nombre}")
    return ruta

def listar_notas_por_fecha():
    """Lista las notas ordenadas de la MÁS NUEVA a la más vieja"""
    ruta_dir = "notas"
    archivos = [os.path.join(ruta_dir, f) for f in os.listdir(ruta_dir) if f.endswith(".txt")]
    archivos.sort(key=os.path.getmtime, reverse=True)
    return [os.path.basename(f).replace(".txt", "") for f in archivos]

def cargar_nota_por_nombre(nombre):
    ruta = f"notas/{nombre}.txt"
    if not os.path.exists(ruta): return None
    with open(ruta, "r", encoding="utf-8") as f:
        return f.read()

def seleccionar_nota_guardada():
    notas = listar_notas_por_fecha()
    
    if not notas:
        hablar("No tienes notas guardadas.")
        return None

    hablar("Tus últimas notas son:")
    # Listamos las notas
    for i, n in enumerate(notas[:5], 1):
        nombre_limpio = n.replace("_", " ").replace(".txt", "")
        hablar(f"Número {i}: {nombre_limpio}")

    hablar("¿Cuál quieres abrir? Di el número o el nombre.")

    for intento in range(3): 
        comando = escuchar_comando().lower()
        
        if not comando:
            if intento < 2: hablar("No te escuché. Di el número de nuevo.")
            continue

        # ESTRATEGIA 1: Selección por Número
        indice = convertir_texto_a_numero(comando)
        if indice and 1 <= indice <= len(notas):
            nota_elegida = notas[indice - 1]
            hablar(f"Abriendo la nota {indice}...")
            return nota_elegida

        # ESTRATEGIA 2: Búsqueda por Nombre
        comando_limpio = comando.replace(" ", "").replace("_", "")
        for nota in notas:
            nota_limpia = nota.lower().replace("_", "").replace(" ", "")
            if comando_limpio in nota_limpia or nota_limpia in comando_limpio:
                return nota
        
        if intento < 2:
            hablar("No entendí cuál. Intenta decir solo el número (ej: 'dos').")

    hablar("No seleccionaste ninguna nota. Volviendo al inicio.")
    return None

def manejar_nota_anterior(nota_actual, nota_guardada):
    if nota_actual and not nota_guardada:
        hablar("Tienes una nota sin guardar. ¿La guardo o la borro?")
        resp = escuchar_comando()
        if any(x in resp for x in ["guardar", "si", "sí"]):
            nombre = pedir_nombre_archivo()
            guardar_archivo(nombre, nota_actual)
            return "", True, "" 
        elif any(x in resp for x in ["borrar", "descartar", "no"]):
            hablar("Nota descartada.")
            return "", False, ""
        else:
            hablar("Manteniendo nota actual.")
            return nota_actual, False, ""
    return nota_actual, nota_guardada, ""

# ========================
# 7. BUCLE PRINCIPAL
# ========================

def asistente():
    hablar("Asistente de notas listo. Di 'graba nota', 'abrir nota' o 'ayuda'.")

    nota_actual = ""
    resumen_actual = ""
    nota_guardada = False

    cmd_grabar = ["graba", "nueva", "dictar"]
    cmd_resumir = ["resumen", "resumir", "analizar"]
    cmd_leer = ["leer", "lee la nota"]
    cmd_guardar = ["guardar", "salvar"]
    cmd_abrir = ["abrir", "cargar", "notas guardadas"]
    cmd_salir = ["salir", "adiós", "terminar"]

    while True:
        comando = escuchar_comando()
        if not comando: continue

        # ---- GRABAR ----
        if any(c in comando for c in cmd_grabar):
            nota_actual, nota_guardada, resumen_actual = manejar_nota_anterior(nota_actual, nota_guardada)
            if not nota_actual:
                texto_nuevo = grabar_y_transcribir_whisper()
                if texto_nuevo:
                    nota_actual = texto_nuevo
                    nota_guardada = False
                    resumen_actual = ""
                    palabras = contar_palabras(nota_actual)
                    hablar(f"Nota capturada ({palabras} palabras).")

        # ---- RESUMIR ----
        elif any(c in comando for c in cmd_resumir):
            if nota_actual:
                hablar("Consultando a la nube...")
                resumen_actual = generar_resumen_groq(nota_actual)
                hablar("Análisis listo:")
                print(f"\n💡 ANÁLISIS:\n{resumen_actual}\n")
                hablar("Te leo el resumen.")
                solo_resumen = resumen_actual.split("TAREAS")[0]
                hablar(solo_resumen) 
            else:
                hablar("No hay nota para resumir.")

        # ---- GUARDAR ----
        elif any(c in comando for c in cmd_guardar):
            if nota_actual:
                nombre = pedir_nombre_archivo()
                contenido = f"TRANSCRIPCIÓN:\n{nota_actual}\n\nANÁLISIS (Groq):\n{resumen_actual}"
                guardar_archivo(nombre, contenido)
                nota_guardada = True
            else:
                hablar("Nada que guardar.")

        # ---- LEER ----
        elif any(c in comando for c in cmd_leer):
            if nota_actual:
                lectura_limpia = nota_actual.replace("TRANSCRIPCIÓN:", "").replace("ANÁLISIS (Groq):", "Resumen:")
                hablar(lectura_limpia)
            else:
                hablar("La memoria está vacía.")

        # ---- ABRIR (POR FECHA) ----
        elif any(c in comando for c in cmd_abrir):
            if nota_actual and not nota_guardada:
                hablar("Primero guarda o descarta tu nota actual.")
                continue
            nombre = seleccionar_nota_guardada()
            if nombre:
                contenido = cargar_nota_por_nombre(nombre)
                if contenido:
                    nota_actual = contenido
                    nota_guardada = True
                    resumen_actual = "" 
                    hablar(f"Nota '{nombre}' cargada.")

        # ---- AYUDA ----
        elif "ayuda" in comando:
            hablar("Comandos: Graba nota, Resumen, Guardar, Abrir nota, Salir.")

        # ---- SALIR ----
        elif any(c in comando for c in cmd_salir):
            if nota_actual and not nota_guardada:
                hablar("Nota sin guardar. ¿Salir igual?")
                resp = escuchar_comando()
                if "si" not in resp and "sí" not in resp:
                    continue
            hablar("Apagando.")
            break

if __name__ == "__main__":
    asistente()