"use client";

import { useEffect, useRef, useMemo, useCallback } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MarkerType,
  type OnSelectionChangeParams,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import "@/styles/reactflow-overrides.css";
import { useWorkflowStore } from "@/stores/workflowStore";
import type { StageId } from "@/types/stage";
import PipelineNode from "./PipelineNode";

const nodeTypes = { pipelineNode: PipelineNode };

function ReactFlowCanvasInner() {
  const nodes = useWorkflowStore((s) => s.nodes);
  const edges = useWorkflowStore((s) => s.edges);
  const selectNode = useWorkflowStore((s) => s.selectNode);
  const reactFlowInstance = useRef<any>(null);
  const isInitialized = useRef(false);

  // Stable edges with smooth step styling
  const styledEdges: Edge[] = useMemo(
    () =>
      edges.map((e) => ({
        ...e,
        type: "smoothstep",
        animated: false,
        style: { stroke: "#2a2a3c", strokeWidth: 2 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: "#2a2a3c",
        },
      })),
    [edges],
  );

  // Fit view on initial render
  useEffect(() => {
    if (reactFlowInstance.current && !isInitialized.current) {
      isInitialized.current = true;
      setTimeout(() => reactFlowInstance.current?.fitView({ padding: 0.3 }), 100);
    }
  }, [nodes.length]);

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      selectNode(node.id as StageId);
    },
    [selectNode],
  );

  const handlePaneClick = useCallback(() => {
    selectNode(null);
  }, [selectNode]);

  const onSelectionChange = useCallback(
    ({ nodes: selectedNodes }: OnSelectionChangeParams) => {
      if (selectedNodes.length > 0) {
        selectNode(selectedNodes[0].id as StageId);
      }
    },
    [selectNode],
  );

  return (
    <ReactFlow
      nodes={nodes}
      edges={styledEdges}
      onNodesChange={() => {}}
      onEdgesChange={() => {}}
      onNodeClick={handleNodeClick}
      onPaneClick={handlePaneClick}
      onSelectionChange={onSelectionChange}
      onInit={(instance) => {
        reactFlowInstance.current = instance;
      }}
      nodeTypes={nodeTypes}
      fitView
      panOnDrag
      zoomOnScroll
      minZoom={0.3}
      maxZoom={2}
      defaultViewport={{ x: 200, y: 80, zoom: 0.85 }}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable
      preventScrolling={false}
    >
      <Background gap={16} size={1} color="#2a2a3c" />
      <Controls />
    </ReactFlow>
  );
}

export default function ReactFlowCanvas() {
  return (
    <div className="h-full w-full">
      <ReactFlowProvider>
        <ReactFlowCanvasInner />
      </ReactFlowProvider>
    </div>
  );
}
