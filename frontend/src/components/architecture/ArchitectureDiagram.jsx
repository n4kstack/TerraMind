import React, { useMemo } from 'react';

const LAYER_ORDER = ['ui', 'business', 'data', 'external'];

const NODE_WIDTH = 220;
const NODE_HEIGHT = 64;
const X_GAP = 26;
const LAYER_Y_GAP = 180;
const MARGIN_X = 40;
const MARGIN_Y = 56;

function edgePath(source, target) {
  const sx = source.x + NODE_WIDTH / 2;
  const sy = source.y + NODE_HEIGHT;
  const tx = target.x + NODE_WIDTH / 2;
  const ty = target.y;
  const c1y = sy + Math.max(24, (ty - sy) * 0.45);
  const c2y = ty - Math.max(24, (ty - sy) * 0.45);
  return `M ${sx} ${sy} C ${sx} ${c1y}, ${tx} ${c2y}, ${tx} ${ty}`;
}

export default function ArchitectureDiagram({
  snapshot,
  selectedNodeId,
  onSelectNode,
  svgRef,
  fitToView = false,
  zoom = 1,
}) {
  const { nodes, edges, layers, positions, width, height } = useMemo(() => {
    if (!snapshot?.nodes?.length) {
      return {
        nodes: [],
        edges: [],
        layers: [],
        positions: {},
        width: 1200,
        height: 720,
      };
    }

    const grouped = new Map(LAYER_ORDER.map((layer) => [layer, []]));
    snapshot.nodes.forEach((node) => {
      const key = grouped.has(node.layer) ? node.layer : 'business';
      grouped.get(key).push(node);
    });

    for (const layerKey of LAYER_ORDER) {
      grouped.get(layerKey).sort((a, b) => a.path.localeCompare(b.path));
    }

    const maxNodes = Math.max(...LAYER_ORDER.map((layer) => grouped.get(layer).length), 1);
    const widthPx = Math.max(1200, MARGIN_X * 2 + maxNodes * (NODE_WIDTH + X_GAP));
    const heightPx = Math.max(760, MARGIN_Y * 2 + LAYER_ORDER.length * LAYER_Y_GAP + NODE_HEIGHT);

    const pos = {};
    LAYER_ORDER.forEach((layer, layerIdx) => {
      const row = grouped.get(layer);
      const rowWidth = row.length * NODE_WIDTH + Math.max(0, row.length - 1) * X_GAP;
      const startX = Math.max(MARGIN_X, (widthPx - rowWidth) / 2);
      const y = MARGIN_Y + layerIdx * LAYER_Y_GAP;

      row.forEach((node, idx) => {
        pos[node.id] = {
          x: startX + idx * (NODE_WIDTH + X_GAP),
          y,
        };
      });
    });

    const graphEdges = (snapshot.edges || []).filter(
      (edge) => pos[edge.source] && pos[edge.target]
    );

    const layerMeta = LAYER_ORDER.map((layerId, idx) => {
      const fallback = {
        id: layerId,
        label: `${layerId} layer`,
        color:
          layerId === 'ui'
            ? '#38bdf8'
            : layerId === 'business'
              ? '#22c55e'
              : layerId === 'data'
                ? '#f59e0b'
                : '#94a3b8',
      };
      const found = (snapshot.layers || []).find((layer) => layer.id === layerId);
      return {
        ...fallback,
        ...(found || {}),
        y: MARGIN_Y + idx * LAYER_Y_GAP,
      };
    });

    return {
      nodes: snapshot.nodes,
      edges: graphEdges,
      layers: layerMeta,
      positions: pos,
      width: widthPx,
      height: heightPx,
    };
  }, [snapshot]);

  return (
    <div className={`rounded-2xl border border-slate-800/70 bg-slate-950/60 ${fitToView ? 'h-full overflow-hidden' : 'overflow-auto custom-scrollbar max-h-[70vh]'}`}>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${width} ${height}`}
        width={fitToView ? '100%' : width * zoom}
        height={fitToView ? '100%' : height * zoom}
        preserveAspectRatio={fitToView ? 'xMidYMid meet' : 'xMidYMin meet'}
        className={fitToView ? 'w-full h-full' : 'min-w-full min-h-full'}
        role="img"
        aria-label="Architecture node graph"
      >
        <defs>
          <marker id="arch-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b" />
          </marker>
        </defs>

        {layers.map((layer) => (
          <g key={layer.id}>
            <rect
              x={18}
              y={layer.y - 16}
              width={width - 36}
              height={NODE_HEIGHT + 32}
              rx={14}
              fill="rgba(15, 23, 42, 0.32)"
              stroke={layer.color}
              strokeOpacity="0.26"
            />
            <text
              x={30}
              y={layer.y - 24}
              fill={layer.color}
              fontSize="11"
              fontWeight="700"
              letterSpacing="1.1"
            >
              {String(layer.label || layer.id).toUpperCase()}
            </text>
          </g>
        ))}

        {edges.map((edge) => {
          const source = positions[edge.source];
          const target = positions[edge.target];
          if (!source || !target) return null;
          return (
            <path
              key={edge.id}
              d={edgePath(source, target)}
              fill="none"
              stroke="#64748b"
              strokeWidth="1.2"
              strokeOpacity="0.6"
              markerEnd="url(#arch-arrow)"
            />
          );
        })}

        {nodes.map((node) => {
          const position = positions[node.id];
          if (!position) return null;

          const isSelected = node.id === selectedNodeId;
          const roleText = String(node.role || 'module').replace(/_/g, ' ');
          const stroke = node.color || '#94a3b8';

          return (
            <g
              key={node.id}
              transform={`translate(${position.x}, ${position.y})`}
              className="cursor-pointer"
              onClick={() => onSelectNode(node.id)}
            >
              <rect
                x="0"
                y="0"
                width={NODE_WIDTH}
                height={NODE_HEIGHT}
                rx="12"
                fill="rgba(15, 23, 42, 0.92)"
                stroke={stroke}
                strokeWidth={isSelected ? 2.2 : 1.1}
                strokeOpacity={isSelected ? 1 : 0.65}
              />
              <text x="12" y="24" fill="#f8fafc" fontSize="12" fontWeight="700">
                {String(node.label || '').slice(0, 30)}
              </text>
              <text x="12" y="42" fill="#94a3b8" fontSize="10" fontWeight="500">
                {roleText.slice(0, 34)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
