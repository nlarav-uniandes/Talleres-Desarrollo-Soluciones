"""Informe de avance 1 alineado con la propuesta entregada (Tolima y Meta). Lee out/tm_resultados.json."""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Inches, RGBColor, Cm

OUT, DEST = Path(sys.argv[1]), Path(sys.argv[2])
R = {int(k): v for k, v in json.load(open(OUT / "tm_resultados.json")).items()}
T1, T2 = R[1]["tabla"], R[2]["tabla"]
A1, A2 = R[1]["ablacion"], R[2]["ablacion"]
I = R[1]["info"]
MOD = ["XGBoost", "LightGBM", "GAM", "Logistica L2"]
NOM = {"Logistica L2": "Logística L2", "Canal endemico": "Canal endémico"}
nom = lambda n: NOM.get(n, n)
pct = lambda v: f"{100 * v:.1f} %".replace(".", ",")
dec = lambda v, k=3: f"{v:.{k}f}".replace(".", ",")
pp = lambda v: f"{100 * v:.1f}".replace(".", ",")

# figura: inicios detectados por alternativa
fig, axs = plt.subplots(1, 2, figsize=(9, 3.6), sharey=True)
for ax, h, T in zip(axs, (1, 2), (T1, T2)):
    ns = MOD + ["Canal endemico", "Persistencia"]
    x = np.arange(len(ns))
    regla = [T[n]["ini_det"] for n in ns]
    mismo = [T[n].get("ini_det_farcanal", np.nan) for n in ns]
    b1 = ax.bar(x - 0.2, regla, 0.4, color="#3b6ea8", label="Umbral de la regla (FA ≤ canal + 5 pp en validación)")
    b2 = ax.bar(x + 0.2, mismo, 0.4, color="#e0a030", label="Misma tasa de falsas alarmas que el canal en prueba")
    ax.bar_label(b1, fmt="%d", fontsize=7); ax.bar_label(b2, fmt="%d", fontsize=7)
    ax.set_xticks(x, [nom(n).replace(" ", "\n") for n in ns], fontsize=7)
    ax.set_title(f"T+{h} ({R[h]['info']['ini_te']} inicios en prueba)", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
axs[0].set_ylabel("Inicios detectados")
axs[0].set_ylim(0, 135)
h_, l_ = axs[0].get_legend_handles_labels()
fig.legend(h_, l_, fontsize=8, loc="lower center", ncol=2, frameon=False)
fig.tight_layout(rect=(0, 0.08, 1, 1)); fig.savefig(OUT / "tm_inicios.png", dpi=160); plt.close(fig)

from matplotlib.patches import FancyBboxPatch
fig, ax = plt.subplots(figsize=(10, 2.6)); ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(0, 2.6)
cajas = [("Panel mensual\nTolima y Meta\n66 municipios", "#d6e4f0"),
         ("Canal y etiqueta\npor partición\n(ref. ≤ 2021 / ≤ 2023)", "#d6e4f0"),
         ("Entrenamiento\n2007-2021\n4 modelos", "#3b6ea8"),
         ("Validación 2022-2023\nparada temprana,\nPlatt, umbral", "#3b6ea8"),
         ("Prueba 2024-2025\nvs canal endémico\ny persistencia", "#e0a030")]
for i, (t, c) in enumerate(cajas):
    x = 0.1 + i * 2
    ax.add_patch(FancyBboxPatch((x, 0.75), 1.7, 1.3, boxstyle="round,pad=0.05", fc=c, ec="#1f3a5f"))
    ax.text(x + 0.85, 1.4, t, ha="center", va="center", fontsize=8.5,
            color="white" if c == "#3b6ea8" else "black")
    if i < 4:
        ax.annotate("", (x + 2.0, 1.4), (x + 1.78, 1.4), arrowprops=dict(arrowstyle="->", color="#1f3a5f"))
ax.text(5, 0.3, "Ablación: el mismo flujo con XGBoost, agregando historial de casos, canal, estacionalidad y clima",
        ha="center", fontsize=8.5, style="italic")
fig.tight_layout(); fig.savefig(OUT / "tm_flujo.png", dpi=160); plt.close(fig)

doc = Document()
st = doc.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(10.5)
st.paragraph_format.space_after = Pt(4)
for sct in doc.sections:
    sct.top_margin = sct.bottom_margin = Cm(2); sct.left_margin = sct.right_margin = Cm(2.2)


def h(t):
    p = doc.add_heading(t, level=1)
    for r in p.runs:
        r.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F); r.font.name = "Calibri"


def par(t):
    p = doc.add_paragraph(t); p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY


def figura(ruta, n, pie, ancho):
    doc.add_picture(str(ruta), width=Inches(ancho)); doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    c = doc.add_paragraph(f"Figura {n}. {pie}"); c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    c.runs[0].font.size = Pt(9); c.runs[0].italic = True


def tabla(enc, filas, n, pie):
    c = doc.add_paragraph(f"Tabla {n}. {pie}"); c.runs[0].font.size = Pt(9); c.runs[0].italic = True
    t = doc.add_table(rows=1, cols=len(enc)); t.style = "Table Grid"
    for i, x in enumerate(enc):
        cel = t.rows[0].cells[i]; cel.text = x
        sh = OxmlElement("w:shd"); sh.set(qn("w:val"), "clear"); sh.set(qn("w:fill"), "1F3A5F")
        cel._tc.get_or_add_tcPr().append(sh)
        r = cel.paragraphs[0].runs[0]; r.font.bold = True; r.font.size = Pt(8.5); r.font.color.rgb = RGBColor(255, 255, 255)
    for fl in filas:
        cs = t.add_row().cells
        for i, x in enumerate(fl):
            cs[i].text = str(x); cs[i].paragraphs[0].runs[0].font.size = Pt(8.5)
    doc.add_paragraph()


p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("Evaluación de modelos de aprendizaje automático para la detección temprana de brotes de dengue en Tolima y Meta")
r.bold = True; r.font.size = Pt(14); r.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
p = doc.add_paragraph("Informe de avance. Proyecto: despliegue de soluciones. MAIA, Universidad de los Andes")
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p = doc.add_paragraph("Stevan Ramirez Cajamarca, Nicolas Steven Lara Villa, Jersson Mauricio Rodríguez Aponte, "
                      "Sergio Andres Ballesteros Suarez")
p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.runs[0].bold = True
p = doc.add_paragraph("Grupo de Investigación en Biología Matemática y Computacional BIOMAC. Experto: Carlos Andres Bravo Vega")
p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.runs[0].font.size = Pt(9.5)

h("1. Descripción breve de la propuesta de solución")
par("El proyecto evalúa si modelos de aprendizaje automático pueden anticipar el inicio de brotes de dengue en los "
    "municipios de Tolima y Meta, y si aportan algo frente al canal endémico que ya usa la vigilancia. El problema se "
    "plantea como una clasificación binaria por municipio y mes: con la información disponible al cierre de un mes se "
    "estima la probabilidad de que el mes siguiente (T+1) o el subsiguiente (T+2) supere el percentil 75 del canal "
    "endémico del propio municipio. La dificultad central no es distinguir meses con muchos o pocos casos, sino separar "
    "el inicio de un brote de su continuación, porque un episodio dura varios meses y las continuaciones son las que la "
    "autoridad sanitaria ya conoce. Por eso la métrica principal es la sensibilidad sobre inicios, y la propuesta fija "
    "tres condiciones para declarar utilidad: superar al canal endémico y a la persistencia en inicios detectados, sin "
    "aumentar la tasa de falsas alarmas en más de cinco puntos porcentuales respecto del canal. El trabajo sigue "
    "CRISP-DM (Chapman et al., 2000) y el modelo elegido se expondrá como servicio de consulta en contenedores.")

h("2. Recolección y preparación de los datos")
par("Las notificaciones de dengue (evento 210) y dengue grave (evento 220) entre 2007 y 2025 se tomaron de SIVIGILA en "
    "Datos Abiertos Colombia (Instituto Nacional de Salud, 2025). Las variables climáticas se extrajeron con Google Earth "
    "Engine: temperatura media, punto de rocío, humedad del suelo, evaporación, escorrentía, viento zonal y meridional y "
    "radiación solar de ERA5-Land (Muñoz-Sabater, 2019), y precipitación de CHIRPS (Funk et al., 2015). Las fuentes se "
    "integran por código DIVIPOLA, los datos crudos se versionan con DVC y un script reproduce la descarga.")
par("En la preparación los casos se ubican por fecha de inicio de síntomas, los códigos de municipio se normalizan a "
    "cinco dígitos, se descartan los registros sin municipio válido y los meses sin notificación se completan con cero "
    "explícito para que rezagos y medias móviles tengan sentido. El panel de Tolima y Meta tiene 78 municipios y 17.784 "
    "registros mensuales, con 244.219 casos de dengue y 4.836 de dengue grave. Aplicando el criterio de endemicidad (casos "
    "en al menos diez años y 200 o más acumulados) quedan 66 municipios. Las variables predictoras se agrupan en cuatro "
    "bloques, que son los que usa la ablación: historial de casos (rezagos de 1, 2, 3, 4 y 6 meses de casos clásicos y "
    "graves y suma móvil de tres meses, 12 variables), canal endémico (P25, P75, zona, razón de incidencia estandarizada y "
    "estado de brote actual y del mes anterior, 9), estacionalidad circular (2) y clima (9 variables del mes y rezagos de 1 "
    "a 3 meses de temperatura y precipitación, 15). El conteo del mes en curso no se usa porque llega incompleto.")
par("Lo que cambió en este avance frente a la versión previa es el tratamiento de la fuga temporal. Canal, razón de "
    "incidencia, endemicidad y etiqueta se recalculan por partición con solo años anteriores: la referencia 2007-2021 "
    "define entrenamiento y validación, y la referencia 2007-2023 define la prueba. Así ningún umbral que entra en la "
    "etiqueta ha visto el periodo que se evalúa.")
tabla(["Partición", "Años objetivo", "Referencia del canal", "Meses-municipio", "Inicios", "Prevalencia de exceso"],
      [["Entrenamiento", "2007-2021", "2007-2021", f"{I['tr']:,}".replace(",", "."), f"{I['ini_tr']:,}".replace(",", "."), pct(I["prev_tr"])],
       ["Validación", "2022-2023", "2007-2021", f"{I['va']:,}".replace(",", "."), str(I["ini_va"]), pct(I["prev_va"])],
       ["Prueba", "2024-2025", "2007-2023", f"{I['te']:,}".replace(",", "."), str(I["ini_te"]), pct(I["prev_te"])]],
      1, "Particiones temporales sobre los 66 municipios endémicos, horizonte T+1.")
par(f"El faltante climático es de {pct(I['clima_na'])} y por ahora se deja explícito, que los modelos de árboles manejan "
    "de forma nativa y que en GAM y logística se imputa con la mediana del entrenamiento. La comparación de las tres "
    "estrategias previstas (explícito, interpolación por municipio y mediana de vecinos) queda para la siguiente etapa.")

h("3. Descripción del proceso de construcción de los modelos")
par("La construcción sigue un flujo único para todos los modelos y horizontes, de modo que lo único que cambia entre "
    "corridas es el modelo o el grupo de variables (Figura 1). El flujo parte del panel mensual, recalcula el canal "
    "endémico y la etiqueta con la referencia de cada partición, entrena sobre 2007-2021, usa 2022-2023 para la parada "
    "temprana, la elección de hiperparámetros, la calibración y el umbral, y evalúa una sola vez sobre 2024-2025 contra "
    "las dos líneas base. La prueba no interviene en ninguna decisión del modelo.")
figura(OUT / "tm_flujo.png", 1, "Flujo de construcción y evaluación de los modelos.", 6.3)
par("Las tres familias se eligieron por complejidad e interpretabilidad decrecientes, tal como plantea la propuesta, y "
    "ninguna se da por ganadora de antemano. El gradient boosting sobre árboles, con XGBoost (Chen y Guestrin, 2016) y "
    "LightGBM (Ke et al., 2017), captura interacciones no lineales entre rezagos, posición en el canal y clima, y maneja "
    "el faltante de forma nativa. El modelo aditivo generalizado (Hastie y Tibshirani, 1986) permite efectos no lineales "
    "pero aditivos, de modo que la curva de cada variable se puede leer por separado, lo que interesa a un usuario de "
    "salud pública. La regresión logística con penalización L2 sirve de referencia lineal: si los modelos complejos no la "
    "superan, la complejidad no se justifica. Los hiperparámetros usados se resumen en la Tabla 2.")
tabla(["Modelo", "Configuración", "Selección"],
      [["XGBoost", "Profundidad 4, tasa 0,05, hasta 500 árboles, submuestreo de filas y columnas 0,8, histograma", "Parada temprana a 40 rondas por PR-AUC en validación"],
       ["LightGBM", "15 hojas, mínimo 40 filas por hoja, tasa 0,05, hasta 500 árboles, submuestreo 0,8", "Parada temprana a 40 rondas en validación"],
       ["GAM (pyGAM)", "Splines de 6 nodos en variables continuas, 4 en indicadores de brote, factor en las zonas del canal; imputación por mediana y estandarización", "Penalización entre 1, 10 y 100 por PR-AUC en validación"],
       ["Logística L2", "Imputación por mediana, estandarización, penalización L2", "C entre 0,01, 0,1 y 1 por PR-AUC en validación"],
       ["Calibración", "Platt scaling sobre las probabilidades de validación", "Ajustada en 2022-2023"],
       ["Umbral", "Mínimo umbral con falsas alarmas ≤ canal + 5 pp en validación", "Elegido en 2022-2023"]],
      2, "Configuración de los modelos, la calibración y el umbral.")
par("Una diferencia frente a la propuesta debe quedar explícita. La propuesta plantea elegir los hiperparámetros con "
    "ventana expansiva sobre el entrenamiento. En esta primera versión la configuración de XGBoost y LightGBM quedó fija, "
    "con una profundidad y un número de hojas moderados para el tamaño del panel, y solo se ajustaron el número de "
    "árboles por parada temprana y las penalizaciones de GAM y logística sobre la validación 2022-2023. La búsqueda con "
    "ventana expansiva queda para la siguiente iteración y se discute en la sección 5.")
par("Las probabilidades de los cuatro modelos se recalibran con Platt scaling sobre 2022-2023 (Niculescu-Mizil y "
    "Caruana, 2005). El umbral de decisión también se fija en validación y traduce la tercera condición de la propuesta: "
    "es el umbral más bajo cuya tasa de falsas alarmas no supera la del canal endémico más cinco puntos, lo que maximiza "
    "los inicios detectados dentro de ese margen. Como líneas base se evalúan, sobre las mismas filas, el canal endémico "
    "(alerta si los casos del mes en curso ya superan el P75 del mes objetivo) y la persistencia (alerta si el mes en "
    "curso ya está en exceso). Para separar el efecto del modelo del efecto del umbral se reporta además cuántos inicios "
    "detecta cada modelo cuando se iguala en prueba la tasa de falsas alarmas del canal. Por último, la ablación agrega "
    "los grupos de variables uno por uno sobre XGBoost, partiendo del modelo que solo usa el historial de casos.")

h("4. Resultados obtenidos")


def filas(T):
    o = []
    for n in MOD + ["Canal endemico", "Persistencia"]:
        r = T[n]
        o.append([nom(n), dec(r["auroc"]), dec(r["sens"]), pct(r["far"]), f"{int(r['ini_det'])} ({pct(r['sens_ini'])})",
                  str(int(r["ini_det_farcanal"])) if "ini_det_farcanal" in r else "-",
                  dec(r["brier_cal"]) if "brier_cal" in r else "-"])
    return o


enc = ["Modelo", "AUROC", "Sensibilidad", "Falsas alarmas", "Inicios detectados", "Inicios a FA del canal", "Brier"]
tabla(enc, filas(T1), 3, f"Prueba 2024-2025, T+1 ({I['ini_te']} inicios). El límite de falsas alarmas es "
      f"{pct(T1['Canal endemico']['far'] + 0.05)}.")
tabla(enc, filas(T2), 4, f"Prueba 2024-2025, T+2 ({R[2]['info']['ini_te']} inicios). El límite es "
      f"{pct(T2['Canal endemico']['far'] + 0.05)}.")
figura(OUT / "tm_inicios.png", 2, "Inicios de brote detectados en prueba con el umbral de la regla y a igual tasa de falsas alarmas que el canal.", 6.2)
par(f"Las cuatro familias quedan muy cerca entre sí. En T+1 LightGBM detecta {int(T1['LightGBM']['ini_det'])} inicios y "
    f"XGBoost {int(T1['XGBoost']['ini_det'])}, frente a {int(T1['Canal endemico']['ini_det'])} del canal endémico y cero "
    f"de la persistencia, que por construcción no puede detectar un inicio a un mes. Las dos primeras condiciones se "
    f"cumplen. La tercera no: la tasa de falsas alarmas de XGBoost es {pct(T1['XGBoost']['far'])}, "
    f"{pp(T1['XGBoost']['far'] - T1['Canal endemico']['far'])} puntos por encima del canal, aunque en validación el "
    f"umbral respetaba el margen. Cuando se iguala la tasa de falsas alarmas del canal, ningún modelo lo supera: XGBoost "
    f"detecta {int(T1['XGBoost']['ini_det_farcanal'])} inicios y LightGBM {int(T1['LightGBM']['ini_det_farcanal'])}, "
    f"contra {int(T1['Canal endemico']['ini_det'])}. En T+2 el patrón se repite ({int(T2['XGBoost']['ini_det'])} contra "
    f"{int(T2['Canal endemico']['ini_det'])} con la regla, {int(T2['XGBoost']['ini_det_farcanal'])} a igual tasa de "
    f"falsas alarmas). La recalibración baja el Brier de XGBoost en T+1 de {dec(T1['XGBoost']['brier_raw'])} a "
    f"{dec(T1['XGBoost']['brier_cal'])}. La Figura 3 muestra que, después de recalibrar, las probabilidades de los tres "
    f"tipos de modelo siguen en general la diagonal. Entre 0,2 y 0,55 la frecuencia observada queda algo por encima de "
    f"lo predicho, es decir que los modelos subestiman levemente el riesgo, coherente con el aumento de prevalencia "
    f"entre validación y prueba.")
figura(OUT / "tm_calibracion.png", 3, "Curvas de calibración en prueba después de Platt scaling, T+1.", 3.6)


def fab(A):
    return [[n, dec(r["auroc"]), pct(r["far"]), f"{int(r['ini_det'])}", str(int(r["ini_det_farcanal"]))] for n, r in A.items()]


tabla(["Variables (XGBoost)", "AUROC", "Falsas alarmas", "Inicios con la regla", "Inicios a FA del canal"],
      fab(A1), 5, "Ablación por grupos de variables, prueba 2024-2025, T+1.")
par(f"La ablación muestra dónde está la señal. Agregar el canal endémico al historial de casos sube el AUROC de "
    f"{dec(A1['Solo historial de casos']['auroc'])} a {dec(A1['+ canal endemico']['auroc'])}, mientras que la "
    f"estacionalidad y el clima no lo mueven ({dec(A1['+ clima (todas)']['auroc'])} con todas las variables). A igual "
    f"tasa de falsas alarmas que el canal, el modelo con solo el historial de casos detecta "
    f"{int(A1['Solo historial de casos']['ini_det_farcanal'])} inicios y el que excluye el canal pero incluye clima "
    f"{int(A1['Casos + estacionalidad + clima, sin canal']['ini_det_farcanal'])}, ligeramente más que el modelo completo "
    f"({int(A1['+ clima (todas)']['ini_det_farcanal'])}).")
figura(OUT / "tm_importancia.png", 4, "Importancia de variables de XGBoost en T+1.", 4.3)

h("5. Análisis de los resultados obtenidos")
par("El hallazgo principal es que en esta primera versión los modelos no aportan sobre el canal endémico en la detección "
    "de inicios. Detectan más inicios que el canal solo porque alertan más, y a igual costo en falsas alarmas detectan "
    f"menos. La importancia de variables lo explica: el estado de exceso del mes en curso concentra el {pct(0.634)} de la "
    "ganancia de XGBoost, seguido de la razón de incidencia y la zona del canal. El modelo aprendió sobre todo a prolongar "
    "el estado actual, que sirve para las continuaciones pero no para anticipar un inicio. Que el modelo sin variables "
    "del canal detecte más inicios a igual tasa de falsas alarmas sugiere que esas variables empujan hacia la "
    "persistencia, y es la pista más concreta para la siguiente iteración.")
per = {(d["anio"], d["modelo"]): d for d in R[1]["periodo"]}
par(f"El segundo reto es el cambio de prevalencia entre periodos, que la propuesta ya anticipaba. El exceso pasa de "
    f"{pct(I['prev_tr'])} en entrenamiento a {pct(I['prev_va'])} en validación y {pct(I['prev_te'])} en prueba, con 2024 "
    f"en {pct(per[(2024, 'XGBoost')]['prev'])} y 2025 en {pct(per[(2025, 'XGBoost')]['prev'])}. Un umbral que respeta el "
    f"margen en validación lo excede en prueba, y el resultado cambia por año: en 2024 XGBoost detecta "
    f"{per[(2024, 'XGBoost')]['ini_det']} de {per[(2024, 'XGBoost')]['inicios']} inicios frente a "
    f"{per[(2024, 'Canal endemico')]['ini_det']} del canal, mientras que en 2025 detecta {per[(2025, 'XGBoost')]['ini_det']} "
    f"de {per[(2025, 'XGBoost')]['inicios']} frente a {per[(2025, 'Canal endemico')]['ini_det']}. Con 172 inicios en prueba "
    "la incertidumbre de la sensibilidad ronda siete puntos, de modo que las diferencias entre familias no son "
    "distinguibles, pero la brecha frente al canal a igual tasa de falsas alarmas sí es apreciable.")
par("El tercer reto es de datos. El aporte del clima es nulo en esta versión, coherente con Beal et al. (2025), que "
    "encontraron que a uno y dos meses el historial reciente concentra la señal y el clima aporta sobre todo a tres y "
    "seis meses. Falta además comparar las estrategias de imputación del faltante climático, verificar el quiebre de 2011 "
    "en la definición de dengue grave y probar la sensibilidad de las conclusiones a la parametrización del canal "
    "(Umaña et al., 2026).")
par("Los próximos pasos, alineados con el cronograma, son cuatro. Primero, cambiar la formulación para que el modelo no "
    "pueda apoyarse en la persistencia: entrenar y evaluar solo sobre los meses que no están en exceso, que son los "
    "únicos donde puede ocurrir un inicio, con la etiqueta de inicio como objetivo. Segundo, elegir el umbral con "
    "ventana expansiva sobre varios años de validación y con la función de costo explícita de la propuesta, para que la "
    "tasa de falsas alarmas sea estable entre años de prevalencia distinta, y ajustar hiperparámetros con esa misma "
    "validación. Tercero, ejecutar los dos experimentos del 3 al 16 de noviembre: aporte de cada grupo de variables con "
    "horizontes más largos y sensibilidad a la ventana del canal, al tratamiento de años epidémicos y a la serie que "
    "define el exceso. Cuarto, seleccionar el modelo, desplegar el servicio de consulta con FastAPI y Docker a partir de "
    "la arquitectura del prototipo, y reportar los resultados estratificados por perfil de municipio.")

h("Referencias")
refs = [
    "Beal, M. R. W., Osorio, J., Ciuoderis, K., Hernandez-Ortiz, J. P., y Block, P. (2025). Forecasting dengue: Evaluating the role of hydroclimate information in subseasonal to seasonal prediction. GeoHealth, 9(9), e2024GH001325. https://doi.org/10.1029/2024GH001325",
    "Chapman, P., Clinton, J., Kerber, R., Khabaza, T., Reinartz, T., Shearer, C., y Wirth, R. (2000). CRISP-DM 1.0: Step-by-step data mining guide. SPSS.",
    "Chen, T., y Guestrin, C. (2016). XGBoost: A scalable tree boosting system. En Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining (pp. 785-794). https://doi.org/10.1145/2939672.2939785",
    "Funk, C., Peterson, P., Landsfeld, M., Pedreros, D., Verdin, J., Shukla, S., et al. (2015). The climate hazards infrared precipitation with stations. Scientific Data, 2, 150066. https://doi.org/10.1038/sdata.2015.66",
    "Hastie, T., y Tibshirani, R. (1986). Generalized additive models. Statistical Science, 1(3), 297-310. https://doi.org/10.1214/ss/1177013604",
    "Instituto Nacional de Salud. (2025). Vigilancia rutinaria por evento: dengue y dengue grave [Conjunto de datos]. Datos Abiertos Colombia. https://www.datos.gov.co",
    "Ke, G., Meng, Q., Finley, T., Wang, T., Chen, W., Ma, W., Ye, Q., y Liu, T.-Y. (2017). LightGBM: A highly efficient gradient boosting decision tree. Advances in Neural Information Processing Systems, 30, 3146-3154.",
    "Muñoz-Sabater, J. (2019). ERA5-Land monthly averaged data from 1981 to present. Copernicus Climate Change Service. https://doi.org/10.24381/cds.68d2bb30",
    "Niculescu-Mizil, A., y Caruana, R. (2005). Predicting good probabilities with supervised learning. En Proceedings of the 22nd International Conference on Machine Learning (pp. 625-632). https://doi.org/10.1145/1102351.1102430",
    "Umaña, J. D., Montenegro-Torres, J., Otero, J., Tavera-Cifuentes, M. C., Niño-Machado, N., González-Uribe, C., Cordovez, J. M., y Santos-Vega, M. (2026). Endemic channel parametrization in dengue surveillance: Methodological assessment of retrospective windows, outbreak trends, and zero-case periods in Colombia. JMIR Public Health and Surveillance, 12, e79914. https://doi.org/10.2196/79914",
]
for x in refs:
    p = doc.add_paragraph(x); p.paragraph_format.left_indent = Cm(0.8)
    p.paragraph_format.first_line_indent = Cm(-0.8); p.runs[0].font.size = Pt(9)
doc.save(DEST)
print("ok")
