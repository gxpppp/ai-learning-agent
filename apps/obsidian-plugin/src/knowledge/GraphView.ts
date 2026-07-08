/** Knowledge Graph ItemView — renders D3-force graph, click-to-navigate. */

import * as d3 from "d3";
import { ItemView, Notice, type WorkspaceLeaf } from "obsidian";
import type AILearningAgentPlugin from "../main";

export const GRAPH_VIEW_TYPE = "ai-graph-panel";

interface GraphNode {
  id: string;
  name: string;
  group: string;
  size: number;
  tags: string[];
  parent: string;
}

interface GraphLink {
  source: string;
  target: string;
  value: number;
}

interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
  total_notes: number;
}

export class GraphView extends ItemView {
  plugin: AILearningAgentPlugin;
  private svgEl!: HTMLElement;
  private simulation: d3.Simulation<d3.SimulationNodeDatum, undefined> | null = null;

  constructor(leaf: WorkspaceLeaf, plugin: AILearningAgentPlugin) {
    super(leaf);
    this.plugin = plugin;
    this.navigation = false;
  }

  getViewType(): string {
    return GRAPH_VIEW_TYPE;
  }

  getDisplayText(): string {
    return "Knowledge Graph";
  }

  getIcon(): string {
    return "git-branch";
  }

  async onOpen(): Promise<void> {
    const container = this.containerEl.children[1] as HTMLElement;
    container.empty();
    container.addClass("ai-graph-container");
    container.createEl("div", { cls: "ai-graph-toolbar" }, (toolbar) => {
      toolbar.createEl("button", { text: "Refresh" }, (btn) => {
        btn.onclick = () => this.refresh();
      });
    });
    this.svgEl = container.createDiv({ cls: "ai-graph-svg" });
  }

  async onClose(): Promise<void> {
    if (this.simulation) {
      this.simulation.stop();
      this.simulation = null;
    }
  }

  async refresh(folder?: string): Promise<void> {
    try {
      new Notice("Loading knowledge graph...");
      const port = this.plugin.settings.server.port;
      const url = folder
        ? `http://127.0.0.1:${port}/api/graph/?folder=${encodeURIComponent(folder)}`
        : `http://127.0.0.1:${port}/api/graph/`;
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data: GraphData = await resp.json();
      this.renderGraph(data);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      new Notice(`Graph failed: ${msg}`);
    }
  }

  private renderGraph(data: GraphData): void {
    this.svgEl.empty();
    if (this.simulation) {
      this.simulation.stop();
      this.simulation = null;
    }

    if (data.nodes.length === 0) {
      this.svgEl.createEl("p", {
        text: "No notes found to graph.",
        cls: "ai-graph-empty",
      });
      return;
    }

    const width = this.svgEl.clientWidth || 600;
    const height = Math.max(width * 0.7, 400);

    const svg = d3
      .select(this.svgEl)
      .append("svg")
      .attr("width", width)
      .attr("height", height);

    const g = svg.append("g");

    const color = d3.scaleOrdinal(d3.schemeCategory10);

    const links = data.links.map((d) => ({
      source: d.source,
      target: d.target,
      value: d.value,
    }));

    const nodes = data.nodes.map((d) => ({ ...d }));

    this.simulation = d3
      .forceSimulation(nodes as d3.SimulationNodeDatum[])
      .force(
        "link",
        d3
          .forceLink(links)
          .id((d: d3.SimulationNodeDatum & { id?: string }) => (d as GraphNode).id),
      )
      .force("charge", d3.forceManyBody().strength(-200))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide().radius(20));

    const link = g
      .append("g")
      .selectAll("line")
      .data(links)
      .enter()
      .append("line")
      .attr("stroke", "var(--text-faint)")
      .attr("stroke-width", (d) => Math.min(d.value, 3));

    const node = g
      .append("g")
      .selectAll("circle")
      .data(nodes)
      .enter()
      .append("circle")
      .attr("r", (d) => d.size || 8)
      .attr("fill", (d) => color(d.group))
      .attr("cursor", "pointer")
      .call(
        d3
          .drag<SVGCircleElement, d3.SimulationNodeDatum & GraphNode>()
          .on("start", (event, d) => {
            if (!event.active) this.simulation!.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d) => {
            if (!event.active) this.simulation!.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          }),
      )
      .on("click", (_event, d) => {
        this.openNote(d.id);
      });

    const label = g
      .append("g")
      .selectAll("text")
      .data(nodes)
      .enter()
      .append("text")
      .text((d) => d.name.length > 20 ? d.name.slice(0, 18) + ".." : d.name)
      .attr("font-size", 10)
      .attr("dx", 12)
      .attr("dy", 4)
      .attr("fill", "var(--text-normal)")
      .style("pointer-events", "none");

    const tooltip = d3
      .select(this.svgEl)
      .append("div")
      .attr("class", "ai-graph-tooltip")
      .style("opacity", 0)
      .style("position", "absolute")
      .style("background", "var(--background-secondary)")
      .style("padding", "4px 8px")
      .style("border-radius", "4px")
      .style("font-size", "11px")
      .style("pointer-events", "none");

    node.on("mouseenter", (event, d) => {
      tooltip.transition().duration(200).style("opacity", 0.9);
      tooltip
        .html(`<strong>${d.name}</strong><br/>tags: ${d.tags?.join(", ") || "none"}`)
        .style("left", event.offsetX + 10 + "px")
        .style("top", event.offsetY - 20 + "px");
    });

    node.on("mouseleave", () => {
      tooltip.transition().duration(300).style("opacity", 0);
    });

    this.simulation.on("tick", () => {
      link
        .attr("x1", (d: d3.SimulationLinkDatum<d3.SimulationNodeDatum>) => (d.source as d3.SimulationNodeDatum).x!)
        .attr("y1", (d: d3.SimulationLinkDatum<d3.SimulationNodeDatum>) => (d.source as d3.SimulationNodeDatum).y!)
        .attr("x2", (d: d3.SimulationLinkDatum<d3.SimulationNodeDatum>) => (d.target as d3.SimulationNodeDatum).x!)
        .attr("y2", (d: d3.SimulationLinkDatum<d3.SimulationNodeDatum>) => (d.target as d3.SimulationNodeDatum).y!);

      node.attr("cx", (d: d3.SimulationNodeDatum) => d.x!).attr("cy", (d: d3.SimulationNodeDatum) => d.y!);

      label.attr("x", (d: d3.SimulationNodeDatum) => d.x!).attr("y", (d: d3.SimulationNodeDatum) => d.y!);
    });
  }

  private openNote(notePath: string): void {
    const file = this.app.vault.getAbstractFileByPath(notePath);
    if (file) {
      this.app.workspace.getLeaf().openFile(file);
    } else {
      new Notice(`Note not found: ${notePath}`);
    }
  }
}
