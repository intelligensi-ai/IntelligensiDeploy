interface EffortRingsProps {
  x: number;
  y: number;
}

export function EffortRings({ x, y }: EffortRingsProps) {
  return (
    <g className="effort-rings" transform={`translate(${x} ${y}) rotate(-10)`}>
      <ellipse className="ring ring-high" rx="430" ry="250" />
      <ellipse className="ring ring-medium" rx="290" ry="164" />
      <ellipse className="ring ring-low" rx="150" ry="86" />
      <g className="ring-labels" transform="rotate(10)">
        <text x="112" y="-68">under 30 min</text>
        <text x="250" y="-118">30-60 min</text>
        <text x="390" y="-172">60+ min</text>
      </g>
    </g>
  );
}
