import networkx as nx
import numpy as np
import random


class FlowNetwork:
    """
    Classe che rappresenta una rete di flusso per l'applicazione dell'ACS.
    """

    def __init__(self, file_path=None):
        self.graph = nx.DiGraph()
        self.source_node = None
        self.sink_node = None
        self.node_count = 0
        self.edge_count = 0
        self.theoretical_max_flow = 0.0

        if file_path:
            self.load_from_file(file_path)

    def load_from_file(self, file_path):
        """
        Carica la rete da file con formato specifico per maximum flow.
        """
        with open(file_path, "r") as file:
            self.node_count = int(file.readline().strip())
            self.edge_count = int(file.readline().strip())
            self.source_node = int(file.readline().strip())
            self.sink_node = int(file.readline().strip())

            self.graph.clear()

            for _ in range(self.edge_count):
                source, target, capacity = map(float, file.readline().strip().split())
                self.add_edge(int(source), int(target), capacity)

        self.theoretical_max_flow = self._calculate_theoretical_max_flow()

    def add_edge(self, source, target, capacity):
        """
        Aggiunge un arco con capacità e inizializza i feromoni.
        """
        self.graph.add_edge(
            source,
            target,
            capacity=capacity,  # Capacità residua (dinamica)
            original_capacity=capacity,  # Capacità originale (statica)
            pheromone_level=1.0,  # Livello feromone corrente
            initial_pheromone=1.0,  # Feromone iniziale per reset
        )

    def reset_capacities(self):
        """
        Ripristina le capacità residue ai valori originali.Necessario per resettare lo stato della rete
        tra diverse esecuzioni.
        """
        for source, target in self.graph.edges():
            self.graph[source][target]["capacity"] = self.graph[source][target][
                "original_capacity"
            ]
            self.graph[source][target]["pheromone_level"] = self.graph[source][target][
                "initial_pheromone"
            ]

    def copy(self):
        """
        Crea una copia profonda della rete.
        """
        new_network = FlowNetwork()
        new_network.graph = self.graph.copy()
        new_network.source_node = self.source_node
        new_network.sink_node = self.sink_node
        new_network.node_count = self.node_count
        new_network.edge_count = self.edge_count
        new_network.theoretical_max_flow = self.theoretical_max_flow
        return new_network

    def _calculate_theoretical_max_flow(self):
        """
        Calcola il flusso teorico massimo come min(capacità uscenti da source, capacità entranti in sink).
        """
        if self.source_node is None or self.sink_node is None:
            return 0.0
        source_capacity = sum(
            self.graph[u][v]["original_capacity"]
            for u, v in self.graph.out_edges(self.source_node)
        )
        sink_capacity = sum(
            self.graph[u][v]["original_capacity"]
            for u, v in self.graph.in_edges(self.sink_node)
        )
        return min(source_capacity, sink_capacity)

    def get_successors(self, node):
        """Restituisce i nodi successori di un dato nodo."""
        return list(self.graph.successors(node))

    def get_residual_capacity(self, source, target):
        """
        Restituisce la capacità residua di un arco.
        """
        return self.graph[source][target]["capacity"]

    def get_original_capacity(self, source, target):
        """
        Restituisce la capacità originale di un arco. Usata come informazione euristica η(i,j),
        """
        return self.graph[source][target]["original_capacity"]

    def get_pheromone_level(self, source, target):
        """Restituisce il livello di feromone di un arco."""
        return self.graph[source][target]["pheromone_level"]

    def update_capacity(self, source, target, flow_amount):
        """
        Aggiorna la capacità residua sottraendo il flusso utilizzato.
        """
        self.graph[source][target]["capacity"] -= flow_amount
        self.graph[source][target]["capacity"] = max(
            0.0, self.graph[source][target]["capacity"]
        )

    def update_pheromone(self, source, target, pheromone_delta):
        """Aggiorna il livello di feromone di un arco."""
        self.graph[source][target]["pheromone_level"] += pheromone_delta

    def set_pheromone(self, source, target, pheromone_value):
        """Imposta il livello di feromone di un arco."""
        self.graph[source][target]["pheromone_level"] = pheromone_value

    def evaporate_pheromone(self, evaporation_rate):
        """
        Applica l'evaporazione dei feromoni a tutti gli archi.
        """
        for source, target in self.graph.edges():
            self.graph[source][target]["pheromone_level"] *= 1 - evaporation_rate
            self.graph[source][target]["pheromone_level"] = max(
                self.graph[source][target]["pheromone_level"], 0.01
            )

    def acs_state_transition_rule(
        self, current_node, q0, pheromone_weight=1.0, heuristic_weight=2.0
    ):
        """
        Implementa la regola di transizione di stato dell'ACS.
        DIFFERENZA CON ACS CLASSICO:
        1. Soft exploitation: invece di scegliere deterministicamente il migliore,
           seleziona casualmente tra i top-K candidati per maggiore diversificazione.
        2. L'euristica è basata sulla capacità originale invece che su 1/distanza.
        """
        successors = self.get_successors(current_node)
        if not successors:
            return None

        q = random.random()

        if q <= q0:
            # MODIFICA RISPETTO ALL'ACS CLASSICO: Soft exploitation
            # L'ACS standard sceglierebbe deterministicamente argmax[τ(i,j) * η(i,j)^β]
            # Qui si seleziona casualmente tra i migliori K candidati
            values = []
            for target in successors:
                pheromone = self.get_pheromone_level(current_node, target)
                heuristic = self.get_original_capacity(current_node, target)
                value = (pheromone**pheromone_weight) * (heuristic**heuristic_weight)
                values.append((target, value))

            values.sort(key=lambda x: x[1], reverse=True)
            top_k = min(3, len(values))  # seleziona i top 3
            candidates = [node for node, _ in values[:top_k]]
            return random.choice(candidates)
        else:
            # IDENTICO ALL'ACS CLASSICO: Exploration tramite selezione proporzionale
            return self._proportional_selection(
                current_node, pheromone_weight, heuristic_weight
            )

    def _proportional_selection(self, current_node, pheromone_weight, heuristic_weight):
        """
        Selezione proporzionale basata su feromoni e euristica. L'euristica è la capacità originale.
        """
        successors = self.get_successors(current_node)
        if not successors:
            return None

        values = []
        for target in successors:
            pheromone = self.get_pheromone_level(current_node, target)
            heuristic = self.get_original_capacity(current_node, target)
            value = (pheromone**pheromone_weight) * (heuristic**heuristic_weight)
            values.append(value)

        total = sum(values)
        if total == 0:
            return random.choice(successors)

        probabilities = [v / total for v in values]
        return np.random.choice(successors, p=probabilities)

    def acs_local_pheromone_update(
        self, source, target, local_evaporation_rate, initial_pheromone=1.0
    ):
        """
        Aggiornamento locale dei feromoni durante la costruzione del path.
        """
        current_pheromone = self.get_pheromone_level(source, target)
        new_pheromone = (
            1 - local_evaporation_rate
        ) * current_pheromone + local_evaporation_rate * initial_pheromone
        self.set_pheromone(source, target, new_pheromone)

    def acs_global_pheromone_update(
        self, best_path, best_flow, global_evaporation_rate
    ):
        """
        Aggiornamento globale dei feromoni sul miglior path trovato.
        """
        if not best_path or best_flow <= 0:
            return

        # MODIFICA: Deposito basato sulla differenza dal massimo teorico
        pheromone_deposit = 1.0 / (1.0 + (self.theoretical_max_flow - best_flow))

        for i in range(len(best_path) - 1):
            source, target = best_path[i], best_path[i + 1]
            current_pheromone = self.get_pheromone_level(source, target)
            # Formula standard ACS: τ(i,j) = (1-ρ)τ(i,j) + ρΔτ
            new_pheromone = (
                1 - global_evaporation_rate
            ) * current_pheromone + global_evaporation_rate * pheromone_deposit
            self.set_pheromone(source, target, new_pheromone)

    def update_path_capacities(self, path, path_flow):
        """
        Aggiorna le capacità residue lungo un path utilizzando il flusso calcolato.
        """
        for i in range(len(path) - 1):
            source, target = path[i], path[i + 1]
            self.update_capacity(source, target, path_flow)

    def get_network_info(self):
        """Stampa informazioni sulla rete."""
        print(f"Flow Network - Nodes: {self.node_count}, Edges: {self.edge_count}")
        print(f"Source: {self.source_node}, Sink: {self.sink_node}")
        print(f"Theoretical maximum flow: {self.theoretical_max_flow:.2f}")

    def __str__(self):
        return f"FlowNetwork({self.node_count} nodes, {self.edge_count} edges, source={self.source_node}, sink={self.sink_node})"

    def __repr__(self):
        return self.__str__()
