import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card } from "../components/ui/card.jsx";
import { Container, Spinner, Table, TableBody, TableCell, TableHead, TableRow } from "../components/ui/layout.jsx";
import { Typography } from "../components/ui/typography.jsx";

const seasons = [2021, 2022, 2023, 2024, 2025];

export default function DashboardPage() {
  const [selectedSeason, setSelectedSeason] = useState(2021);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function loadDashboardData() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`/api/dashboard?season=${selectedSeason}`);
        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          throw new Error(body.detail || `Request failed (${response.status})`);
        }
        const result = await response.json();
        if (!cancelled) setData(result);
      } catch (err) {
        if (!cancelled) {
          setData(null);
          setError(err.message || "Unable to load dashboard data.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadDashboardData();
    return () => {
      cancelled = true;
    };
  }, [selectedSeason]);

  const topDrivers = (data?.top_three_drivers || []).map((driver) => ({
    name: driver.driver_name,
    points: Number(driver.points) || 0,
  }));

  return (
    <Container>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <Typography variant="h4" className="mb-1">
            {selectedSeason} Season Dashboard
          </Typography>
          <Typography variant="body2" className="text-gray-400">
            Historical Formula 1 statistics for the selected season.
          </Typography>
        </div>

        <div className="flex gap-2">
          {seasons.map((season) => (
            <button
              key={season}
              type="button"
              onClick={() => setSelectedSeason(season)}
              className={`rounded-md border px-3 py-1.5 text-sm ${
                selectedSeason === season
                  ? "border-accent bg-accent/15 text-accent"
                  : "border-gray-700 text-gray-400 hover:border-gray-500 hover:text-white"
              }`}
            >
              {season}
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div className="flex items-center justify-center gap-3 py-16 text-gray-400">
          <Spinner size={28} />
          Loading dashboard data...
        </div>
      )}

      {!loading && error && (
        <Card className="border-red-500/30 bg-red-500/5">
          <Typography variant="body1" className="mb-1 text-red-300">
            Could not load dashboard data
          </Typography>
          <Typography variant="body2" className="text-gray-400">
            {error}. Make sure the backend is running on port 8000.
          </Typography>
        </Card>
      )}

      {!loading && !error && data && (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard label="Races" value={data.total_races} hint={`Grands Prix in ${selectedSeason}`} />
            <StatCard label="Drivers" value={data.available_drivers} hint="Registered drivers" />
            <StatCard label="Race Results" value={data.total_race_results} hint="Recorded classifications" />
          </div>

          <Card>
            <Typography variant="h5" className="mb-4">
              Recent Race Winners
            </Typography>
            {data.race_winners?.length ? (
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell className="text-xs uppercase text-gray-400">Round</TableCell>
                    <TableCell className="text-xs uppercase text-gray-400">Grand Prix</TableCell>
                    <TableCell className="text-xs uppercase text-gray-400">Winner</TableCell>
                    <TableCell className="text-xs uppercase text-gray-400">Constructor</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.race_winners.map((race, index) => (
                    <TableRow key={`${race.race_name}-${index}`}>
                      <TableCell>{race.round || "—"}</TableCell>
                      <TableCell className="text-white">{race.race_name}</TableCell>
                      <TableCell>{race.winner}</TableCell>
                      <TableCell className="text-gray-400">{race.winner_constructor}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <Typography variant="body2" className="text-gray-500">
                No race winners available for this season.
              </Typography>
            )}
          </Card>

          <div className="grid gap-6 lg:grid-cols-2">
            <StandingsCard
              title="Driver Standings"
              rows={data.driver_championship_standings}
              nameKey="driver_name"
            />
            <StandingsCard
              title="Constructor Standings"
              rows={data.constructor_championship_standings}
              nameKey="constructor_name"
            />
          </div>

          {topDrivers.length > 0 && (
            <Card>
              <Typography variant="h5" className="mb-4">
                Top Three Drivers by Points
              </Typography>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={topDrivers} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                    <CartesianGrid stroke="#27272f" vertical={false} />
                    <XAxis dataKey="name" stroke="#8888a0" tick={{ fontSize: 12 }} />
                    <YAxis stroke="#8888a0" tick={{ fontSize: 12 }} />
                    <Tooltip
                      contentStyle={{ background: "#12121a", border: "1px solid #33333d" }}
                      labelStyle={{ color: "#fff" }}
                    />
                    <Bar dataKey="points" name="Points" fill="#ff2a40" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          )}
        </div>
      )}
    </Container>
  );
}

function StatCard({ label, value, hint }) {
  return (
    <Card>
      <Typography variant="caption" className="uppercase tracking-wide">
        {label}
      </Typography>
      <Typography variant="h3" className="mt-1">
        {value ?? "—"}
      </Typography>
      <Typography variant="body2" className="mt-1 text-gray-500">
        {hint}
      </Typography>
    </Card>
  );
}

function StandingsCard({ title, rows, nameKey }) {
  return (
    <Card>
      <Typography variant="h5" className="mb-4">
        {title}
      </Typography>
      {rows?.length ? (
        <Table>
          <TableHead>
            <TableRow>
              <TableCell className="text-xs uppercase text-gray-400">Pos</TableCell>
              <TableCell className="text-xs uppercase text-gray-400">Name</TableCell>
              <TableCell className="text-right text-xs uppercase text-gray-400">Points</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.slice(0, 10).map((row, index) => (
              <TableRow key={`${row[nameKey]}-${index}`}>
                <TableCell>{row.position || index + 1}</TableCell>
                <TableCell className="text-white">{row[nameKey] || "—"}</TableCell>
                <TableCell className="text-right">{row.points ?? "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <Typography variant="body2" className="text-gray-500">
          No standings available.
        </Typography>
      )}
    </Card>
  );
}
