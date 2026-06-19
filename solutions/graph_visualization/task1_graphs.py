import pandas as pd
import networkx as nx
import plotly.graph_objects as go
import numpy as np
import matplotlib.pyplot as plt

def visualize_graph_1():
    """
    Visualize 13_AdjacencyUndirectedUnweighted.csv
    Undirected, Unweighted Graph
    """
    url = "https://raw.githubusercontent.com/thieu1995/csv-files/main/data/DV-course/13_AdjacencyUndirectedUnweighted.csv"
    # Read the CSV. The first column is the node names.
    df = pd.read_csv(url, index_col=0)
    
    # Fill NA with 0 and convert to integer (1 for edge, 0 for no edge)
    adj_matrix = df.fillna(0).apply(pd.to_numeric, errors='coerce').fillna(0).astype(int)
    
    # Create Graph
    G = nx.from_pandas_adjacency(adj_matrix)
    
    # Plot using NetworkX & Matplotlib for a quick look
    plt.figure(figsize=(12, 10))
    pos = nx.spring_layout(G, k=0.15, iterations=20)
    nx.draw_networkx_nodes(G, pos, node_size=50, node_color='skyblue', alpha=0.8)
    nx.draw_networkx_edges(G, pos, alpha=0.3, edge_color='gray')
    nx.draw_networkx_labels(G, pos, font_size=6, font_family='sans-serif')
    plt.title("Undirected Unweighted Graph (Co-authorship)")
    plt.axis('off')
    plt.savefig('solutions/graph_visualization/undirected_unweighted.png')
    plt.close()

def visualize_graph_2():
    """
    Visualize 13_AdjacencyDirectedWeighted.csv
    Directed, Weighted Graph
    """
    url = "https://raw.githubusercontent.com/thieu1995/csv-files/main/data/DV-course/13_AdjacencyDirectedWeighted.csv"
    df = pd.read_csv(url, index_col=0)
    
    # Create Directed Graph
    G = nx.from_pandas_adjacency(df, create_using=nx.DiGraph)
    
    # visualization using Matplotlib
    plt.figure(figsize=(10, 8))
    pos = nx.circular_layout(G)
    
    # Edge weights for visualization
    edges = G.edges(data=True)
    weights = [d['weight'] * 2 for u, v, d in edges]
    
    nx.draw_networkx_nodes(G, pos, node_size=2000, node_color='orange', alpha=0.9)
    nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold')
    nx.draw_networkx_edges(G, pos, width=weights, arrowstyle='->', arrowsize=20, edge_color='red', alpha=0.5)
    
    edge_labels = nx.get_edge_attributes(G, 'weight')
    nx.draw_networkx_edge_labels(G, pos, edge_labels={k: f"{v:.2f}" for k, v in edge_labels.items()}, font_size=8)
    
    plt.title("Directed Weighted Graph (Regions Flow)")
    plt.axis('off')
    plt.savefig('solutions/graph_visualization/directed_weighted.png')
    plt.close()

def visualize_graph_3():
    """
    Visualize 13_AdjacencyUndirecterWeighted.csv
    Undirected, Weighted Graph (Cities Distances)
    """
    url = "https://raw.githubusercontent.com/thieu1995/csv-files/main/data/DV-course/13_AdjacencyUndirecterWeighted.csv"
    
    # This CSV is a bit messy, let's fix it
    data = pd.read_csv(url)
    # The first column name is messy, let's rename it
    data.columns = ['City'] + list(data.columns[1:])
    data = data.set_index('City')
    
    # Clean data: remove symbols and convert to numeric
    def clean_val(val):
        if pd.isna(val) or val == "" or val == " ": return 0
        if isinstance(val, str):
            # Remove non-numeric characters except handle decimal/scientific
            val = "".join(c for c in val if c.isdigit() or c == '.')
        try:
            return float(val)
        except:
            return 0
            
    df = data.applymap(clean_val)
    
    # Create Graph
    G = nx.from_pandas_adjacency(df)
    
    # Visualization
    plt.figure(figsize=(14, 12))
    pos = nx.kamada_kawai_layout(G) # Better for distance-based graphs
    
    nx.draw_networkx_nodes(G, pos, node_size=500, node_color='lightgreen', alpha=0.8)
    nx.draw_networkx_labels(G, pos, font_size=8)
    
    # Draw edges with opacity based on weight (longer distance = lighter/more transparent)
    edges = G.edges(data=True)
    max_dist = max([d['weight'] for u, v, d in edges]) if edges else 1
    
    for u, v, d in edges:
        # Drawing fewer edges for clarity if it's too dense, or just all with low alpha
        alpha = 1.0 - (d['weight'] / max_dist)
        alpha = max(0.05, alpha * 0.5)
        nx.draw_networkx_edges(G, pos, edgelist=[(u,v)], width=1, alpha=alpha, edge_color='blue')

    plt.title("Undirected Weighted Graph (City Distances)")
    plt.axis('off')
    plt.savefig('solutions/graph_visualization/undirected_weighted.png')
    plt.close()

if __name__ == "__main__":
    print("Generating visualizations...")
    visualize_graph_1()
    print("- Saved undirected_unweighted.png")
    visualize_graph_2()
    print("- Saved directed_weighted.png")
    visualize_graph_3()
    print("- Saved undirected_weighted.png")
    print("Done!")
