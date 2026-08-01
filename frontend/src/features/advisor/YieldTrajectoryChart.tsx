import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

/**
 * District yield trajectory.
 *
 * Plots real historical data from `ten_year_trajectory_data` (parallel `years`
 * and `yields` arrays). Lazily loaded by the parent so Recharts never enters
 * the bundle for users who don't reach a result.
 *
 * Colours are `hsl(var(--token))` rather than literals so the chart follows the
 * light/dark theme without a JS re-render.
 */
export default function YieldTrajectoryChart({
  years,
  yields,
  unit,
}: {
  years: number[];
  yields: number[];
  unit: string;
}) {
  // Guard against ragged arrays: zip to the shorter of the two rather than
  // emitting points with undefined values.
  const length = Math.min(years.length, yields.length);
  const data = Array.from({ length }, (_, i) => ({ year: years[i], yield: yields[i] }));

  if (data.length < 2) return null;

  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
          <defs>
            <linearGradient id="yieldFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.28} />
              <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0.02} />
            </linearGradient>
          </defs>

          <CartesianGrid
            strokeDasharray="3 3"
            stroke="hsl(var(--border))"
            vertical={false}
          />
          <XAxis
            dataKey="year"
            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
            tickLine={false}
            axisLine={{ stroke: 'hsl(var(--border))' }}
            minTickGap={12}
          />
          <YAxis
            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
            tickLine={false}
            axisLine={false}
            width={48}
          />
          <Tooltip
            cursor={{ stroke: 'hsl(var(--primary))', strokeWidth: 1, strokeDasharray: '4 4' }}
            contentStyle={{
              background: 'hsl(var(--card))',
              border: '1px solid hsl(var(--border))',
              borderRadius: 12,
              fontSize: 13,
              color: 'hsl(var(--card-foreground))',
              boxShadow: '0 12px 32px rgba(8,19,13,0.08)',
            }}
            labelStyle={{ color: 'hsl(var(--muted-foreground))', fontWeight: 600 }}
            formatter={(value) => [
              `${typeof value === 'number' ? value.toFixed(2) : String(value)} ${unit}`,
              'Yield',
            ]}
          />
          <Area
            type="monotone"
            dataKey="yield"
            stroke="hsl(var(--primary))"
            strokeWidth={2.5}
            fill="url(#yieldFill)"
            dot={{ r: 3, fill: 'hsl(var(--primary))', strokeWidth: 0 }}
            activeDot={{ r: 5 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
