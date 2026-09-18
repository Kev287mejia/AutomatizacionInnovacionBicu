from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import os

def create_manual():
    doc = SimpleDocTemplate("entrega/BICU_Consolidador_v1.0.1/Manual_de_Usuario.pdf", pagesize=letter)
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    h1_style = styles['Heading1']
    h2_style = styles['Heading2']
    h3_style = styles['Heading3']
    normal_style = styles['Normal']
    
    story = []
    
    # Title
    story.append(Paragraph("Manual de Usuario - BICU Consolidador v1.0.1", title_style))
    story.append(Spacer(1, 12))
    
    story.append(Paragraph("Qué es BICU Consolidador", h1_style))
    story.append(Paragraph("El sistema BICU Consolidador permite tomar las cinco matrices institucionales de BICU, identificarlas automáticamente, consolidar la información correspondiente a un período y generar los informes correspondientes.", normal_style))
    
    story.append(Paragraph("Requisitos", h1_style))
    story.append(Paragraph("• Windows 10/11 de 64 bits.", normal_style))
    story.append(Paragraph("• No requiere instalar Python.", normal_style))
    story.append(Paragraph("• No requiere instalar pip.", normal_style))
    story.append(Paragraph("• No requiere abrir una terminal para utilizar la aplicación.", normal_style))
    
    story.append(Paragraph("Archivos de entrada", h1_style))
    story.append(Paragraph("El sistema trabaja con cinco matrices:", normal_style))
    story.append(Paragraph("• M1 — Consolidado de Actividades.", normal_style))
    story.append(Paragraph("• M2 — Estudiantes.", normal_style))
    story.append(Paragraph("• M3 — Académicos y Administrativos.", normal_style))
    story.append(Paragraph("• M4 — Colaboradores.", normal_style))
    story.append(Paragraph("• M5 — Protagonistas/Beneficiarios.", normal_style))
    story.append(Paragraph("El sistema identifica las matrices por su estructura y NO depende del nombre del archivo ni del orden en que se seleccionen.", normal_style))
    
    story.append(Paragraph("Cómo iniciar el sistema", h1_style))
    story.append(Paragraph("1. Abrir <b>BICU_Consolidador.exe</b>.", normal_style))
    story.append(Paragraph("2. Esperar a que aparezca la ventana.", normal_style))
    story.append(Paragraph("3. Seleccionar/cargar las matrices.", normal_style))
    story.append(Paragraph("4. Identificar las matrices.", normal_style))
    story.append(Paragraph("5. Seleccionar el período.", normal_style))
    story.append(Paragraph("6. Elegir los informes.", normal_style))
    story.append(Paragraph("7. Ejecutar la consolidación.", normal_style))
    story.append(Paragraph("8. Revisar los resultados.", normal_style))
    story.append(Paragraph("9. Abrir los informes generados.", normal_style))
    
    story.append(Paragraph("Selección del período", h1_style))
    story.append(Paragraph("Usted puede seleccionar:", normal_style))
    story.append(Paragraph("• Año", normal_style))
    story.append(Paragraph("• Mes", normal_style))
    story.append(Paragraph("• Semana/período correspondiente", normal_style))
    
    story.append(Paragraph("Selección de productos", h1_style))
    story.append(Paragraph("<b>Informe Técnico de Auditoría:</b> Es el informe orientado a revisión técnica, trazabilidad, métricas y discrepancias.", normal_style))
    story.append(Paragraph("<b>Informe Institucional Ejecutivo:</b> Es el informe destinado a representar la información en el formato institucional semanal aprobado.", normal_style))
    story.append(Paragraph("Pueden seleccionarse solamente Técnico, solamente Institucional, o ambos.", normal_style))
    
    story.append(Paragraph("Discrepancias", h1_style))
    story.append(Paragraph("Una discrepancia significa que existe una diferencia entre la información declarada en M1 y la información nominal encontrada en las matrices de participantes. El sistema NO corrige automáticamente estas diferencias.", normal_style))
    story.append(Paragraph("El Informe Institucional Ejecutivo utiliza DECLARADO_M1 como fuente principal de presentación institucional. La información nominal permanece disponible para trazabilidad/auditoría.", normal_style))
    
    story.append(Paragraph("M5 histórico", h1_style))
    story.append(Paragraph("Los registros históricos de M5 que están fuera del período seleccionado se preservan y no se mezclan artificialmente con las actividades activas del período.", normal_style))
    
    story.append(Paragraph("Estados de resultados", h1_style))
    story.append(Paragraph("• <b>SUCCESS:</b> El proceso finalizó con éxito.", normal_style))
    story.append(Paragraph("• <b>FAILED:</b> Hubo un error en el proceso.", normal_style))
    story.append(Paragraph("• <b>NOT_REQUESTED:</b> No se solicitó la generación de este elemento.", normal_style))
    
    story.append(Paragraph("Problemas comunes", h1_style))
    story.append(Paragraph("• <b>Plantilla vacía:</b> Asegúrese de que el archivo no esté vacío.", normal_style))
    story.append(Paragraph("• <b>Matriz incorrecta:</b> El sistema no pudo identificar el formato. Revise que sea el formato correcto.", normal_style))
    story.append(Paragraph("• <b>Archivos faltantes:</b> Deben cargarse las cinco matrices.", normal_style))
    story.append(Paragraph("• <b>Documento Word abierto/bloqueado:</b> Si el informe final está abierto en Word, ciérrelo para que el sistema pueda sobrescribirlo.", normal_style))
    story.append(Paragraph("• <b>Permisos de escritura:</b> Asegúrese de tener permisos en la carpeta de destino.", normal_style))
    story.append(Paragraph("• <b>Ningún informe seleccionado:</b> Marque al menos un informe a generar.", normal_style))
    
    story.append(Paragraph("Ubicación de resultados", h1_style))
    story.append(Paragraph("Los informes generados quedan en el directorio de salida (output) especificado por el usuario al realizar la consolidacion.", normal_style))
    
    doc.build(story)


def create_guia_rapida():
    doc = SimpleDocTemplate("entrega/BICU_Consolidador_v1.0.1/Guia_Rapida.pdf", pagesize=letter)
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    h1_style = styles['Heading1']
    h2_style = styles['Heading2']
    normal_style = styles['Normal']
    
    story = []
    
    # Title
    story.append(Paragraph("Guía Rápida - BICU Consolidador v1.0.1", title_style))
    story.append(Spacer(1, 12))
    
    story.append(Paragraph("PASO 1", h1_style))
    story.append(Paragraph("Abrir <b>BICU_Consolidador.exe</b>", normal_style))
    
    story.append(Paragraph("PASO 2", h1_style))
    story.append(Paragraph("Seleccionar las cinco matrices.", normal_style))
    
    story.append(Paragraph("PASO 3", h1_style))
    story.append(Paragraph("Ejecutar la identificación automática M1–M5.", normal_style))
    
    story.append(Paragraph("PASO 4", h1_style))
    story.append(Paragraph("Seleccionar año/mes/semana.", normal_style))
    
    story.append(Paragraph("PASO 5", h1_style))
    story.append(Paragraph("Seleccionar:", normal_style))
    story.append(Paragraph("☑ Informe Técnico", normal_style))
    story.append(Paragraph("☑ Informe Institucional", normal_style))
    story.append(Paragraph("o el producto requerido.", normal_style))
    
    story.append(Paragraph("PASO 6", h1_style))
    story.append(Paragraph("Ejecutar consolidación.", normal_style))
    
    story.append(Paragraph("PASO 7", h1_style))
    story.append(Paragraph("Revisar estados.", normal_style))
    
    story.append(Paragraph("PASO 8", h1_style))
    story.append(Paragraph("Abrir el informe correspondiente.", normal_style))
    story.append(Spacer(1, 12))
    
    story.append(Paragraph("<b>Nota:</b> Si el sistema reporta una discrepancia, no significa que haya corregido los datos; significa que existe una diferencia que debe ser revisada.", normal_style))
    
    doc.build(story)

if __name__ == '__main__':
    create_manual()
    create_guia_rapida()
