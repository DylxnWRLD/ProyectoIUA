import os
import speech_recognition as sr
import pyttsx3
import threading
import time
from transformers import pipeline
from datetime import datetime

# ========================
# CONFIGURACIÓN INICIAL
# ========================
r = sr.Recognizer()
r.pause_threshold = 1.5
r.non_speaking_duration = 0.6
r.energy_threshold = 300
r.dynamic_energy_threshold = True

print("Cargando modelo de IA, espera un momento…")

# Usar un modelo más simple y confiable para resúmenes
try:
    summarizer = pipeline(
        "summarization",
        model="Falconsai/text_summarization"
    )
    print("Modelo de resumen cargado correctamente ✅")
except Exception as e:
    print(f"Error cargando el modelo: {e}")
    print("Usando modelo alternativo...")
    try:
        summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
    except:
        summarizer = None
        print("No se pudo cargar ningún modelo de resumen")

os.makedirs("notas", exist_ok=True)

# ========================
# FUNCIONES DE APOYO
# ========================

def reproducir_sonido():
    """Reproduce un sonido para indicar que puede hablar"""
    try:
        # Intentar reproducir un beep simple
        import winsound
        winsound.Beep(1000, 200)  # Frecuencia 1000Hz, duración 200ms
    except:
        # Si no funciona en este sistema, solo imprimir
        print("🔊 ¡Puedes hablar ahora!")

def hablar(texto):
    """Función robusta para hablar - reinicia el motor cada vez"""
    print("🤖:", texto)
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 170)
        engine.setProperty('volume', 1.0)
        engine.say(texto)
        engine.runAndWait()
        engine.stop()
        del engine
    except Exception as e:
        print(f"Error en voz: {e}")

def escuchar():
    """Escucha y reconoce voz del usuario"""
    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source, duration=0.8)
        print("🎙️ Escuchando comando...")
        # Reproducir sonido antes de escuchar
        threading.Thread(target=reproducir_sonido).start()
        try:
            audio = r.listen(source, timeout=10)
        except sr.WaitTimeoutError:
            print("⏰ Tiempo de espera agotado")
            return ""

    try:
        texto = r.recognize_google(audio, language="es-ES").lower()
        print(f"👤: {texto}")
        return texto
    except sr.UnknownValueError:
        print("❌ No se pudo entender el audio")
        return ""
    except sr.RequestError as e:
        print(f"❌ Error en el servicio: {e}")
        return ""

def escuchar_con_intentos(max_intentos=5, mensaje="Por favor, responde:"):
    """Escucha con múltiples intentos si no se entiende"""
    for intento in range(max_intentos):
        if intento > 0:
            hablar(f"Intento {intento + 1} de {max_intentos}. {mensaje}")
        
        texto = escuchar()
        
        if texto and texto.strip():
            return texto.strip()
    
    hablar("No pude entender tu respuesta después de varios intentos. Volviendo al menú principal.")
    return ""

def escuchar_nota():
    """Escucha continuamente y detecta comandos de terminación SIN incluirlos en la nota"""
    nota = ""
    hablar("Comienza a dictar tu nota. Cuando quieras terminar, di: 'terminar nota', 'finalizar' o 'guardar nota'.")
    print("🎙️ Dictado activado...")

    terminaciones = [
        "terminar nota",
        "finalizar nota", 
        "guardar nota",
        "eso es todo",
        "terminar",
        "finalizar",
        "listo"
    ]

    while True:
        with sr.Microphone() as source:
            r.adjust_for_ambient_noise(source, duration=0.5)
            print("🎤 Listo para escuchar...")
            # Sonido antes de cada segmento de dictado
            threading.Thread(target=reproducir_sonido).start()
            try:
                audio = r.listen(source, timeout=15)
            except sr.WaitTimeoutError:
                print("⏰ Tiempo de espera en dictado")
                continue

        try:
            texto = r.recognize_google(audio, language="es-ES").lower()
            print(f"📝: {texto}")

            # Verificar si es un comando de terminación
            if any(terminacion in texto for terminacion in terminaciones):
                hablar("Entendido, terminando la nota.")
                return nota.strip()

            # Si no es comando de terminación, agregar a la nota
            nota += texto + " "
            palabras_actuales = len(nota.split())
            print(f"📄 Nota actual: {palabras_actuales} palabras")
            
            # Informar cada 30 palabras
            if palabras_actuales % 30 == 0:
                hablar(f"Llevas {palabras_actuales} palabras. Puedes continuar o decir 'terminar nota' para finalizar.")

        except sr.UnknownValueError:
            print("❌ No se entendió en dictado")
        except sr.RequestError as e:
            print(f"❌ Error en servicio de dictado: {e}")

def pedir_nombre_archivo():
    """Pide al usuario que diga el nombre del archivo con múltiples intentos"""
    hablar("¿Qué nombre quieres ponerle a esta nota?")
    nombre = escuchar_con_intentos(3, "Di el nombre para la nota:")
    
    if not nombre:
        nombre = datetime.now().strftime("nota_%Y%m%d_%H%M%S")
        hablar(f"Usando nombre automático: {nombre}")
    else:
        nombre = nombre.strip().replace(" ", "_")
    
    return nombre

def seleccionar_nota_guardada():
    """Permite seleccionar una nota guardada con múltiples intentos"""
    notas = listar_notas()
    
    if not notas:
        hablar("No tienes notas guardadas.")
        return None

    hablar("Tus notas disponibles son:")
    for i, n in enumerate(notas[:5], 1):
        hablar(f"{i}. {n}")

    for intento in range(3):
        if intento > 0:
            hablar(f"Intento {intento + 1} de 3. ¿Cuál nota deseas?")
        
        hablar("Di el nombre completo de la nota que quieres:")
        nombre = escuchar().replace(" ", "_")
        
        if nombre in notas:
            return nombre
        
        # También permitir selección por número
        if nombre.isdigit():
            idx = int(nombre) - 1
            if 0 <= idx < len(notas):
                return notas[idx]
        
        # Búsqueda parcial
        coincidencias = [n for n in notas if nombre in n.lower()]
        if len(coincidencias) == 1:
            return coincidencias[0]
        elif len(coincidencias) > 1:
            hablar("Encontré varias coincidencias:")
            for n in coincidencias[:3]:
                hablar(n)
            continue
    
    hablar("No pude identificar la nota después de varios intentos.")
    return None

def guardar_archivo(nombre, contenido):
    ruta = f"notas/{nombre}.txt"
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(contenido)
    hablar(f"Archivo guardado como {nombre}")
    return ruta

def listar_notas():
    archivos = os.listdir("notas")
    return [a.replace(".txt", "") for a in archivos if a.endswith(".txt")]

def cargar_nota_por_nombre(nombre):
    ruta = f"notas/{nombre}.txt"
    if not os.path.exists(ruta):
        return None
    with open(ruta, "r", encoding="utf-8") as f:
        return f.read()

def contar_palabras(texto):
    """Cuenta las palabras en un texto"""
    return len(texto.split())

def leer_nota_completa(contenido, nombre_nota):
    """Lee una nota completa de forma optimizada"""
    palabras = contar_palabras(contenido)
    hablar(f"Leyendo nota completa '{nombre_nota}'. Tiene {palabras} palabras.")
    
    # Si es muy larga, dividir en secciones
    if palabras > 100:
        hablar("La nota es larga, la leeré por secciones...")
        
        # Dividir en párrafos u oraciones
        lineas = contenido.split('\n')
        secciones = []
        
        for linea in lineas:
            if linea.strip():
                # Dividir línea larga en chunks
                palabras_linea = linea.split()
                if len(palabras_linea) > 30:
                    for i in range(0, len(palabras_linea), 30):
                        chunk = " ".join(palabras_linea[i:i+30])
                        secciones.append(chunk)
                else:
                    secciones.append(linea)
        
        # Leer secciones con pausas
        for i, seccion in enumerate(secciones):
            if seccion.strip():
                hablar(seccion)
                # Pequeña pausa entre secciones largas
                if i < len(secciones) - 1 and len(seccion.split()) > 20:
                    time.sleep(1)
    else:
        # Nota corta, leer completa
        hablar(contenido)
    
    hablar("Fin de la nota.")

def generar_resumen_simple(texto):
    """Genera un resumen simple y confiable"""
    try:
        palabras = contar_palabras(texto)
        
        if palabras < 30:
            return "La nota es demasiado corta para generar un resumen significativo."
        
        # Para textos cortos, usar las primeras oraciones
        if palabras < 100:
            oraciones = texto.split('.')
            if len(oraciones) > 2:
                return '. '.join(oraciones[:2]) + '.'
            else:
                return texto
        
        # Para textos más largos, dividir y tomar partes clave
        palabras_clave = texto.split()
        if len(palabras_clave) > 150:
            # Tomar inicio, medio y final
            tercio = len(palabras_clave) // 3
            resumen_palabras = (
                palabras_clave[:tercio//2] + 
                palabras_clave[tercio:tercio + tercio//2] + 
                palabras_clave[-tercio//2:]
            )
            return " ".join(resumen_palabras) + "..."
        else:
            # Para textos medianos, tomar el 60%
            cantidad_resumen = int(len(palabras_clave) * 0.6)
            return " ".join(palabras_clave[:cantidad_resumen]) + "..."
            
    except Exception as e:
        print(f"Error generando resumen simple: {e}")
        return "No pude generar un resumen para esta nota."

def generar_resumen_ia(texto):
    """Intenta generar resumen con IA, falla silenciosamente a resumen simple"""
    if summarizer is None:
        return generar_resumen_simple(texto)
    
    try:
        palabras = contar_palabras(texto)
        
        if palabras < 30:
            return "La nota es demasiado corta para un resumen de IA."
        
        # Configuración para el modelo
        max_length = min(150, palabras // 2)
        min_length = min(50, palabras // 4)
        
        resultado = summarizer(
            texto,
            max_length=max_length,
            min_length=min_length,
            do_sample=False,
            length_penalty=2.0,
            num_beams=4
        )
        
        resumen = resultado[0].get("summary_text", "").strip()
        
        # Verificar si el resumen tiene sentido
        if resumen and len(resumen.split()) >= 5:
            return resumen
        else:
            return generar_resumen_simple(texto)
            
    except Exception as e:
        print(f"Error en resumen IA: {e}")
        return generar_resumen_simple(texto)

def manejar_nota_anterior(nota_actual, nota_guardada):
    """Maneja qué hacer con una nota anterior no guardada"""
    if nota_actual and not nota_guardada:
        palabras = contar_palabras(nota_actual)
        hablar(f"Tienes una nota sin guardar de {palabras} palabras.")
        hablar("¿Quieres guardarla, descartarla o continuar con ella?")
        
        for intento in range(3):
            respuesta = escuchar_con_intentos(1, "Di 'guardar', 'descartar' o 'continuar':")
            
            if any(p in respuesta for p in ["guardar", "salvar"]):
                nombre = pedir_nombre_archivo()
                guardar_archivo(nombre, nota_actual)
                hablar("Nota anterior guardada. Comenzando nueva nota...")
                return "", True, ""  # nota_actual, nota_guardada, resumen_actual
            elif any(p in respuesta for p in ["descartar", "eliminar", "borrar"]):
                hablar("Nota anterior descartada. Comenzando nueva nota...")
                return "", False, ""  # Limpiar todo
            elif any(p in respuesta for p in ["continuar", "seguir"]):
                hablar("Continuando con la nota actual...")
                return nota_actual, False, ""  # Mantener nota actual
            else:
                hablar("No entendí tu respuesta. Por favor di 'guardar', 'descartar' o 'continuar'.")
        
        hablar("Volviendo al menú principal sin cambios.")
        return nota_actual, False, ""  # Mantener estado actual
    
    return nota_actual, nota_guardada, ""  # No hay cambios

# ========================
# FUNCIONALIDAD PRINCIPAL
# ========================

def asistente():
    hablar("Hola, soy tu asistente de notas. Di 'graba nota' o 'ayuda'.")

    nota_actual = ""
    resumen_actual = ""
    nota_guardada = False

    comandos_cargar_nota = ["abrir nota", "cargar nota", "nota guardada", "leer una nota guardada"]
    comandos_resumir_guardada = ["resumir nota guardada", "resumen de nota guardada"]

    comandos_grabar = ["graba nota", "nueva nota", "dictar nota", "anotar algo"]
    comandos_resumen = ["resumen", "resúmelo", "resumir", "resume la nota"]
    comandos_leer_nota = ["leer nota", "léela", "lee la nota"]
    comandos_leer_resumen = ["lee el resumen", "léeme el resumen"]
    comandos_guardar_nota = ["guardar nota", "salvar nota"]
    comandos_guardar_resumen = ["guardar resumen", "salvar resumen"]
    comandos_ayuda = ["ayuda", "qué puedes hacer", "comandos"]
    comandos_salir = ["salir", "adiós", "cerrar asistente"]

    while True:
        comando = escuchar()
        
        if not comando:
            continue

        # ---- GRABAR NOTA ----
        if any(c in comando for c in comandos_grabar):
            # Manejar nota anterior si existe
            if nota_actual and not nota_guardada:
                nota_actual, nota_guardada, resumen_actual = manejar_nota_anterior(nota_actual, nota_guardada)
            
            # Si después de manejar la nota anterior no tenemos nota (fue descartada o guardada)
            # o si no había nota anterior, entonces grabar nueva
            if not nota_actual:
                nueva_nota = escuchar_nota()
                if nueva_nota:
                    nota_actual = nueva_nota
                    nota_guardada = False
                    resumen_actual = ""
                    palabras = contar_palabras(nota_actual)
                    hablar(f"Nota guardada en memoria. Tienes {palabras} palabras. Para guardarla permanentemente di 'guaradar nota'")
                else:
                    hablar("No se capturó contenido para la nota.")
            else:
                # Si tenemos nota actual (usuario eligió "continuar"), preguntar si quiere reemplazar
                hablar("Ya tienes una nota en memoria. ¿Quieres reemplazarla con una nueva?")
                respuesta = escuchar_con_intentos(2, "Di 'sí' para reemplazar o 'no' para mantenerla:")
                if any(p in respuesta for p in ["sí", "si", "reemplazar"]):
                    nueva_nota = escuchar_nota()
                    if nueva_nota:
                        nota_actual = nueva_nota
                        nota_guardada = False
                        resumen_actual = ""
                        palabras = contar_palabras(nota_actual)
                        hablar(f"Nueva nota guardada en memoria. Tienes {palabras} palabras. Para guardarla permanentemente di 'guaradar nota'")
                    else:
                        hablar("No se capturó contenido para la nueva nota.")
                else:
                    hablar("Manteniendo la nota actual.")

        # ---- LEER NOTA ACTUAL ----
        elif any(c in comando for c in comandos_leer_nota):
            if nota_actual:
                palabras = contar_palabras(nota_actual)
                estado = "guardada" if nota_guardada else "sin guardar"
                hablar(f"Esta es tu nota actual de {palabras} palabras ({estado}):")
                if palabras > 50:
                    hablar("Leyendo los puntos principales...")
                    preview = " ".join(nota_actual.split()[:50]) + "..."
                    hablar(preview)
                else:
                    hablar(nota_actual)
            else:
                hablar("No hay ninguna nota en memoria. Primero graba una nota.")

        # ---- RESUMIR NOTA ACTUAL ----
        elif any(c in comando for c in comandos_resumen):
            if nota_actual:
                palabras = contar_palabras(nota_actual)
                
                if palabras < 20:
                    hablar("La nota es muy corta para resumir. Necesita al menos 20 palabras.")
                else:
                    hablar("Generando resumen...")
                    resumen_actual = generar_resumen_ia(nota_actual)
                    hablar("Resumen listo:")
                    hablar(resumen_actual)
            else:
                hablar("Primero graba una nota para poder resumirla.")

        # ---- LEER RESUMEN ACTUAL ----
        elif any(c in comando for c in comandos_leer_resumen):
            if resumen_actual:
                palabras = contar_palabras(resumen_actual)
                hablar(f"Este es el resumen de {palabras} palabras:")
                hablar(resumen_actual)
            else:
                hablar("No hay un resumen generado. Primero di 'resumen' para generar uno.")

        # ---- GUARDAR NOTA ----
        elif any(c in comando for c in comandos_guardar_nota):
            if nota_actual:
                if nota_guardada:
                    hablar("Esta nota ya está guardada.")
                    continue
                    
                palabras = contar_palabras(nota_actual)
                hablar(f"Tu nota tiene {palabras} palabras.")
                nombre = pedir_nombre_archivo()
                contenido_completo = f"NOTA COMPLETA ({palabras} palabras):\n{nota_actual}\n\n"
                if resumen_actual:
                    palabras_resumen = contar_palabras(resumen_actual)
                    contenido_completo += f"RESUMEN ({palabras_resumen} palabras):\n{resumen_actual}"
                else:
                    contenido_completo += "RESUMEN: No generado"
                
                guardar_archivo(nombre, contenido_completo)
                nota_guardada = True
            else:
                hablar("No hay nota para guardar.")

        # ---- LEER NOTA GUARDADA ----
        elif any(c in comando for c in comandos_cargar_nota):
            nombre = seleccionar_nota_guardada()
            
            if nombre:
                contenido = cargar_nota_por_nombre(nombre)
                if contenido:
                    palabras = contar_palabras(contenido)
                    hablar(f"Nota '{nombre}' cargada. Tiene {palabras} palabras.")
                    
                    # Preguntar si quieren reemplazar la nota actual
                    if nota_actual and not nota_guardada:
                        hablar("¿Quieres reemplazar tu nota actual sin guardar con esta nota guardada?")
                        respuesta = escuchar_con_intentos(2, "Di 'sí' para reemplazar o 'no' para solo leerla:")
                        if any(p in respuesta for p in ["sí", "si", "reemplazar"]):
                            nota_actual = contenido
                            nota_guardada = True
                            resumen_actual = ""
                            hablar("Nota actual reemplazada por la nota guardada.")
                    
                    # NUEVAS OPCIONES MEJORADAS
                    hablar("¿Qué quieres hacer con esta nota?")
                    hablar("Di 'leer nota completa' para escuchar toda la nota")
                    hablar("O di 'generar resumen' para crear un resumen")
                    
                    respuesta = escuchar_con_intentos(2, "Di 'leer nota completa' o 'generar resumen':")
                    
                    if any(p in respuesta for p in ["leer nota completa", "leer completa", "nota completa", "leer todo"]):
                        if palabras > 300:
                            hablar("La nota es muy larga. ¿Estás seguro de que quieres escucharla completa?")
                            confirmacion = escuchar_con_intentos(1, "Di 'sí' para continuar o 'no' para cancelar:")
                            if any(p in confirmacion for p in ["sí", "si"]):
                                leer_nota_completa(contenido, nombre)
                            else:
                                hablar("Entendido, cancelando lectura completa.")
                        else:
                            leer_nota_completa(contenido, nombre)
                    
                    elif any(p in respuesta for p in ["generar resumen", "hacer resumen", "resumen", "resumir"]):
                        if palabras >= 20:
                            hablar("Generando resumen...")
                            resumen_temp = generar_resumen_ia(contenido)
                            hablar("Resumen generado:")
                            hablar(resumen_temp)
                        else:
                            hablar("Esta nota es muy corta para resumir.")
                    else:
                        hablar("No entendí tu elección. Mostrando un fragmento de la nota:")
                        lineas = contenido.split('\n')
                        for linea in lineas[:2]:
                            if linea.strip() and len(linea) > 10:
                                hablar(linea[:80] + "...")

        # ---- RESUMIR NOTA GUARDADA ----
        elif any(c in comando for c in comandos_resumir_guardada):
            nombre = seleccionar_nota_guardada()
            
            if nombre:
                contenido = cargar_nota_por_nombre(nombre)
                if contenido:
                    palabras = contar_palabras(contenido)
                    if palabras < 20:
                        hablar("Esta nota es muy corta para resumir.")
                    else:
                        hablar(f"Generando resumen para nota de {palabras} palabras...")
                        resumen = generar_resumen_ia(contenido)
                        hablar("Resumen generado:")
                        hablar(resumen)

        # ---- AYUDA ----
        elif any(c in comando for c in comandos_ayuda):
            mensajes_ayuda = [
                "Puedo ayudarte con:",
                "Grabar notas - di 'graba nota'",
                "Leer nota actual - di 'lee la nota'",  
                "Generar resumen - di 'resumen'",
                "Guardar nota - di 'guardar nota'",
                "Abrir notas - di 'abrir nota'",
                "Salir - di 'salir'"
            ]
            
            for mensaje in mensajes_ayuda:
                hablar(mensaje)

        # ---- SALIR ----
        elif any(c in comando for c in comandos_salir):
            if nota_actual and not nota_guardada:
                palabras = contar_palabras(nota_actual)
                hablar(f"Tienes una nota sin guardar de {palabras} palabras.")
                respuesta = escuchar_con_intentos(2, "¿Quieres guardarla antes de salir? Di 'sí' o 'no':")
                if any(p in respuesta for p in ["sí", "si"]):
                    nombre = pedir_nombre_archivo()
                    guardar_archivo(nombre, nota_actual)
            
            hablar("Hasta luego. Fue un placer ayudarte.")
            break

        else:
            hablar("No entendí ese comando. Di 'ayuda' para ver opciones.")

# ========================
# EJECUCIÓN
# ========================
if __name__ == "__main__":
    try:
        asistente()
    except KeyboardInterrupt:
        print("\n👋 Programa interrumpido por el usuario")
    except Exception as e:
        print(f"❌ Error crítico: {e}")