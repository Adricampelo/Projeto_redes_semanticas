import ifcopenshell  # Importa a biblioteca para manipulação de arquivos IFC
import networkx as nx  # Importa o NetworkX para criação e manipulação de grafos
import plotly.graph_objects as go  # Importa Plotly para visualização gráfica interativa

# Caminho para seu arquivo
IFC_PATH = "D:/IFCGraph/modelos/Building-Architecture.ifc"  # Define o caminho do arquivo IFC

# Carrega o arquivo IFC
print("Carregando modelo IFC...")  # Exibe mensagem de carregamento
ifc = ifcopenshell.open(IFC_PATH)  # Abre o arquivo IFC usando ifcopenshell
print("Arquivo carregado!")  # Confirma que o arquivo foi carregado

# Cria o grafo direcionado
G = nx.DiGraph()  # Inicializa um grafo direcionado

# Adiciona elementos do modelo ao grafo
for rel in ifc.by_type("IfcRelAggregates"):  # Itera sobre todas as relações de agregação
    parent = rel.RelatingObject  # Obtém o objeto pai
    for child in rel.RelatedObjects:  # Itera sobre os objetos filhos
        G.add_node(str(parent.GlobalId), label=parent.is_a())  # Adiciona o nó do pai ao grafo
        G.add_node(str(child.GlobalId), label=child.is_a())  # Adiciona o nó do filho ao grafo
        G.add_edge(str(parent.GlobalId), str(child.GlobalId), relation="aggregates")  # Cria aresta de agregação

for rel in ifc.by_type("IfcRelContainedInSpatialStructure"):  # Itera sobre relações espaciais
    parent = rel.RelatingStructure  # Obtém a estrutura espacial pai
    for child in rel.RelatedElements:  # Itera sobre os elementos contidos
        G.add_node(str(parent.GlobalId), label=parent.is_a())  # Adiciona o nó do pai
        G.add_node(str(child.GlobalId), label=child.is_a())  # Adiciona o nó do filho
        G.add_edge(str(parent.GlobalId), str(child.GlobalId), relation="contains")  # Cria aresta de contenção

# Posição dos nós
pos = nx.spring_layout(G, k=0.3, seed=42)  # Calcula a posição dos nós para visualização

# Separar arestas por tipo para cores diferentes
edge_x = {"aggregates": [], "contains": []}  # Inicializa dicionário para coordenadas X das arestas
edge_y = {"aggregates": [], "contains": []}  # Inicializa dicionário para coordenadas Y das arestas

for u, v, data in G.edges(data=True):  # Itera sobre todas as arestas do grafo
    x0, y0 = pos[u]  # Pega a posição do nó de origem
    x1, y1 = pos[v]  # Pega a posição do nó de destino
    edge_x[data["relation"]].extend([x0, x1, None])  # Adiciona coordenadas X para a aresta
    edge_y[data["relation"]].extend([y0, y1, None])  # Adiciona coordenadas Y para a aresta

# Cria traces para as arestas coloridas
edge_trace_agg = go.Scatter(
    x=edge_x["aggregates"], y=edge_y["aggregates"],  # Coordenadas das arestas de agregação
    line=dict(width=2, color='blue'),  # Define cor e largura da linha
    hoverinfo='none',  # Sem informação ao passar o mouse
    mode='lines',  # Modo de exibição em linhas
    name='Aggregates'  # Nome da legenda
)

edge_trace_cont = go.Scatter(
    x=edge_x["contains"], y=edge_y["contains"],  # Coordenadas das arestas de contenção
    line=dict(width=2, color='green'),  # Define cor e largura da linha
    hoverinfo='none',  # Sem informação ao passar o mouse
    mode='lines',  # Modo de exibição em linhas
    name='Contains'  # Nome da legenda
)

# Nós
node_x = []  # Lista para coordenadas X dos nós
node_y = []  # Lista para coordenadas Y dos nós
node_text = []  # Lista para textos dos nós

for node in G.nodes():  # Itera sobre todos os nós do grafo
    x, y = pos[node]  # Obtém a posição do nó
    node_x.append(x)  # Adiciona coordenada X
    node_y.append(y)  # Adiciona coordenada Y
    label = G.nodes[node]['label']  # Obtém o tipo do nó
    node_text.append(f"{label}\nID: {node}")  # Monta o texto do nó

node_trace = go.Scatter(
    x=node_x, y=node_y,  # Coordenadas dos nós
    mode='markers+text',  # Exibe marcadores e texto
    hoverinfo='text',  # Mostra texto ao passar o mouse
    textposition='top center',  # Posição do texto
    text=node_text,  # Texto dos nós
    marker=dict(
        showscale=False,  # Não mostra escala de cor
        color='orange',  # Cor dos nós
        size=20,  # Tamanho dos nós
        line_width=2  # Largura da borda dos nós
    ),
    name='Nodes'  # Nome da legenda
)

# Layout do gráfico
fig = go.Figure(data=[edge_trace_agg, edge_trace_cont, node_trace],  # Adiciona os traces ao gráfico
                layout=go.Layout(
                    title='Grafo IFC Interativo',  # Título do gráfico
                    title_x=0.5,  # Centraliza o título
                    showlegend=True,  # Exibe a legenda
                    hovermode='closest',  # Hover mais próximo
                    margin=dict(b=20,l=5,r=5,t=40),  # Margens do gráfico
                    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),  # Oculta grade e eixos X
                    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)   # Oculta grade e eixos Y
                ))

fig.show()  # Exibe o gráfico interativo
