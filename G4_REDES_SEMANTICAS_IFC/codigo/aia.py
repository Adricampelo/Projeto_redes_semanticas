# Bibliotecas principais para a aplicação
import streamlit as st
import ifcopenshell
from rdflib import Graph, Namespace, URIRef, Literal, RDF, XSD
import tempfile
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components
from fpdf import FPDF
import re

# UTILITÁRIOS 
def carregar_modelo_ifc(uploaded_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".ifc") as tmp_file:
        tmp_file.write(uploaded_file.read())
        return ifcopenshell.open(tmp_file.name)

def inicializar_rdf(model):
    # Inicializa um grafo RDF com namespace próprio
    ns = Namespace("http://example.org/ifc/")
    g = Graph()
    g.bind("ns", ns)
    g.bind("xsd", XSD)
    entidades = []

    # Para cada elemento do tipo IfcProduct, cria triplas RDF com seu tipo e nome
    for el in model.by_type("IfcProduct"):
        if not el.GlobalId:
            continue
        uri = URIRef(ns[el.GlobalId])
        g.add((uri, RDF.type, URIRef(ns[el.is_a()])))
        if el.Name:
            g.add((uri, ns["name"], Literal(el.Name)))
        entidades.append((uri, el))

    return g, ns, entidades

# VISUALIZAÇÃO
# Constrói um grafo direcionado a partir do grafo RDF
def mostrar_grafo(rdf_graph):
    G = nx.DiGraph()
    for s, p, o in rdf_graph:
        s_label = str(s).split("/")[-1]
        p_label = str(p).split("/")[-1]
        if isinstance(o, URIRef):
            o_label = str(o).split("/")[-1]
            G.add_edge(s_label, o_label, label=p_label)
        else:
            G.add_node(s_label)
        # Cria visualização com Pyvis
    net = Network(height="500px", width="100%", directed=True)
    net.from_nx(G)
    net.save_graph("grafo_semantico.html")
    components.html(open("grafo_semantico.html", "r", encoding="utf-8").read(), height=600)

def mostrar_detalhes_elemento(entidades):
    selecionado = st.selectbox("Selecione um elemento:", [str(el[0]).split("/")[-1] for el in entidades])
    for uri, el in entidades:
        if selecionado == str(uri).split("/")[-1]:
            st.markdown(f"**Tipo**: `{el.is_a()}`")
            st.markdown(f"**GlobalId**: `{el.GlobalId}`")
            st.json({k: str(v) for k, v in el.get_info().items() if v})

# REGRAS
def regra_nt11(model, rdf_graph, ns):
    st.subheader("Regra NT-11: Largura das Saídas")
    # Atribui uma lotação padrão de 50 pessoas para cada espaço
    for espaco in model.by_type("IfcSpace"):
        uri = URIRef(ns[espaco.GlobalId])
        rdf_graph.add((uri, ns["lotacao"], Literal(50, datatype=XSD.integer)))

    # Adiciona a largura das portas ao grafo RDF

    for porta in model.by_type("IfcDoor"):
        if porta.OverallWidth is not None:
            uri = URIRef(ns[porta.GlobalId])
            rdf_graph.add((uri, ns["largura"], Literal(porta.OverallWidth, datatype=XSD.float)))

# Consulta SPARQL para verificar se a largura total de saídas é suficiente
    query = """
    PREFIX ns: <http://example.org/ifc/>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    SELECT ?espaco ?lotacao ?larguraTotal (xsd:float(?lotacao) * 0.01 AS ?larguraNecessaria)
    WHERE {
        ?espaco a ns:IfcSpace ;
                ns:lotacao ?lotacao .
        {
            SELECT ?espaco (SUM(?largura) AS ?larguraTotal)
            WHERE {
                ?espaco a ns:IfcSpace .
                ?porta a ns:IfcDoor ;
                       ns:largura ?largura .
            }
            GROUP BY ?espaco
        }
    }
    """
# Executa a consulta e exibe os resultados
    try:
        resultados = rdf_graph.query(query)
        for row in resultados:
            nome = str(row.espaco).split("/")[-1]
            largura_total = float(row.larguraTotal)
            largura_necessaria = float(row.lotacao) * 0.01
            conforme = largura_total >= largura_necessaria
            texto = (
                f"Espaço: {nome}\n"
                f"- Lotação: {row.lotacao} pessoas\n"
                f"- Largura necessária: {largura_necessaria:.2f} m\n"
                f"- Largura total de portas: {largura_total:.2f} m\n"
                f"- Resultado: {'Conforme' if conforme else 'Não conforme'}"
            )
            st.text(texto)
            st.session_state.relatorio_resultados.append(texto)
    except Exception as e:
        st.error(f"Erro: {e}")

def regra_nt21(model):
    # Verifica se os extintores estão posicionados a alturas aceitáveis
    resultados = []
    conforme = 0
    nao_conforme = 0

    for ext in model.by_type("IfcFireSuppressionTerminal"):
        placement = ext.ObjectPlacement
        altura = None
        if hasattr(placement, "RelativePlacement") and hasattr(placement.RelativePlacement, "Location"):
            coords = placement.RelativePlacement.Location.Coordinates
            if len(coords) > 2:
                altura = float(coords[2])
                esta_conforme = 0.10 <= altura <= 1.60
                texto = (
                    f"Extintor {ext.GlobalId}\n"
                    f"- Altura: {altura:.2f} m\n"
                    f"- Resultado: {'Conforme' if esta_conforme else 'Não conforme'}")
                resultados.append(texto)
                if esta_conforme:
                    conforme += 1
                else:
                    nao_conforme += 1

    for linha in resultados:
        st.text(linha)
        st.session_state.relatorio_resultados.append(linha)

    return resultados, conforme, nao_conforme

def regra_nt20(model):
    # Verifica se as portas de saída possuem sinalização (baseado no ID)
    resultados = []
    conforme = 0
    nao_conforme = 0

    saidas = model.by_type("IfcDoor")
    sinais = model.by_type("IfcAnnotation")

    for porta in saidas:
        # Considera que um sinal está relacionado se compartilha o prefixo do ID
        possui_sinal = any(porta.GlobalId[:4] in sinal.GlobalId for sinal in sinais)
        texto = (
            f"Porta {porta.GlobalId}\n"
            f"- Resultado: {'Conforme' if possui_sinal else 'Não conforme'}"
        )
        resultados.append(texto)
        if possui_sinal:
            conforme += 1
        else:
            nao_conforme += 1

    for linha in resultados:
        st.text(linha)
        st.session_state.relatorio_resultados.append(linha)

    return resultados, conforme, nao_conforme

# RELATÓRIO PDF
def gerar_pdf_relatorio():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Relatório Geral de Verificações", ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Arial", "", 12)
    pdf.multi_cell(0, 10, "Este relatório apresenta os resultados das verificações automáticas com base no modelo IFC.")
    pdf.ln(5)

# Contagem de conformidades
    conforme_total = sum(1 for linha in st.session_state.relatorio_resultados if "Resultado: Conforme" in linha)
    nao_conforme_total = sum(1 for linha in st.session_state.relatorio_resultados if "Resultado: Não conforme" in linha)
# Adiciona cada linha de resultado
    for linha in st.session_state.relatorio_resultados:
        pdf.multi_cell(0, 10, linha)

    pdf.ln(10)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Resumo Final", ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, f"Total de itens conformes: {conforme_total}", ln=True)
    pdf.cell(0, 10, f"Total de itens NÃO conformes: {nao_conforme_total}", ln=True)
# Salva e oferece botão para download
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
        pdf.output(tmp_pdf.name)
        with open(tmp_pdf.name, "rb") as f:
            st.download_button("Baixar Relatório PDF", file_name="relatorio_geral.pdf", data=f.read())

# INTERFACE PRINCIPAL
def main():
    st.set_page_config(page_title="AIA Semântica", layout="wide")

    if "relatorio_resultados" not in st.session_state:
        st.session_state.relatorio_resultados = []

    st.title("🏗️AIA Maranhão: Análise de Incêndio Automatizada")
# Menu lateral para escolha da página
    pagina = st.sidebar.selectbox("Escolha uma página", [
        "Visualização Semântica",
        "Regras NT-11",
        "Regras NT-21",
        "Regras NT-20",
        "Relatório Geral"
    ])
# Upload de arquivo IFC
    uploaded_file = st.sidebar.file_uploader("Carregue seu arquivo IFC", type="ifc")

    if uploaded_file:
        model = carregar_modelo_ifc(uploaded_file)
        rdf_graph, ns, entidades = inicializar_rdf(model)
 # Direciona para a página selecionada
        if pagina == "Visualização Semântica":
            mostrar_grafo(rdf_graph)
            mostrar_detalhes_elemento(entidades)
        elif pagina == "Regras NT-11":
            regra_nt11(model, rdf_graph, ns)
        elif pagina == "Regras NT-21":
            regra_nt21(model)
        elif pagina == "Regras NT-20":
            regra_nt20(model)
        elif pagina == "Relatório Geral":
            if st.button("Gerar PDF do Relatório"):
                gerar_pdf_relatorio()
# Executa a aplicação
if __name__ == "__main__":
    main()
