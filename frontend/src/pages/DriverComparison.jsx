import { useEffect, useState } from "react";
import { Card } from "../components/ui/card.jsx";
import {
  Container,
  Select,
  Spinner,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
} from "../components/ui/layout.jsx";
import { Typography } from "../components/ui/typography.jsx";

const metrics = [
  { key: "total_races", label: "Races" },
  { key: "wins", label: "Wins" },
  { key: "podiums", label: "Podiums" },
  { key: "points_total", label: "Points" },
  { key: "average_position", label: "Average finish" },
];

export default function DriverComparison() {
  const [drivers, setDrivers] = useState([]);
  const [driver1, setDriver1] = useState("");
  const [driver2, setDriver2] = useState("");
  const [stats, setStats] = useState({});
  const [loadingDrivers, setLoadingDrivers] = useState(true);
  const [loadingStats, setLoadingStats] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function loadDrivers() {
      setLoadingDrivers(true);
      setError(null);
      try {
        const response = await fetch("/api/drivers");
        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          throw new Error(body.detail || `Request failed (${response.status})`);
        }
        const data = await response.json();
        if (cancelled) return;
        setDrivers(Array.isArray(data) ? data : []);
        if (data.length >= 2) {
          setDriver1(data[0].driver_id);
          setDriver2(data[1].driver_id);
        }
      } catch (err) {
        if (!cancelled) setError(err.message || "Unable to load drivers.");
      } finally {
        if (!cancelled) setLoadingDrivers(false);
      }
    }

    loadDrivers();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadStats() {
      if (!driver1 || !driver2) {
        setStats({});
        return;
      }

      setLoadingStats(true);
      setError(null);
      try {
        const [first, second] = await Promise.all([
          fetch(`/api/drivers/${driver1}`),
          fetch(`/api/drivers/${driver2}`),
        ]);

        if (!first.ok || !second.ok) {
          throw new Error("Driver statistics are not available for this selection.");
        }

        const [firstStats, secondStats] = await Promise.all([
          first.json(),
          second.json(),
        ]);

        if (!cancelled) {
          setStats({ [driver1]: firstStats, [driver2]: secondStats });
        }
      } catch (err) {
        if (!cancelled) {
          setStats({});
          setError(err.message || "Unable to load comparison.");
        }
      } finally {
        if (!cancelled) setLoadingStats(false);
      }
    }

    loadStats();
    return () => {
      cancelled = true;
    };
  }, [driver1, driver2]);

  const firstStats = stats[driver1];
  const secondStats = stats[driver2];

  return (
    <Container>
      <Typography variant="h4" className="mb-1">
        Driver Comparison
      </Typography>
      <Typography variant="body2" className="mb-6 text-gray-400">
        Compare career statistics for two drivers in the 2021–2025 dataset.
      </Typography>

      {loadingDrivers && (
        <div className="flex items-center gap-3 py-10 text-gray-400">
          <Spinner size={24} />
          Loading drivers...
        </div>
      )}

      {!loadingDrivers && (
        <div className="space-y-6">
          <Card>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Typography variant="body2" className="mb-2 text-gray-400">
                  Driver 1
                </Typography>
                <Select
                  value={driver1}
                  onValueChange={setDriver1}
                  className="w-full"
                >
                  <option value="">Select driver...</option>
                  {drivers.map((driver) => (
                    <option key={driver.driver_id} value={driver.driver_id}>
                      {driver.driver_name}
                    </option>
                  ))}
                </Select>
              </div>

              <div>
                <Typography variant="body2" className="mb-2 text-gray-400">
                  Driver 2
                </Typography>
                <Select
                  value={driver2}
                  onValueChange={setDriver2}
                  className="w-full"
                >
                  <option value="">Select driver...</option>
                  {drivers.map((driver) => (
                    <option key={driver.driver_id} value={driver.driver_id}>
                      {driver.driver_name}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
          </Card>

          {error && (
            <Card className="border-red-500/30 bg-red-500/5">
              <Typography variant="body2" className="text-red-300">
                {error}
              </Typography>
            </Card>
          )}

          {loadingStats && (
            <div className="flex items-center gap-3 py-6 text-gray-400">
              <Spinner size={20} />
              Loading comparison...
            </div>
          )}

          {!loadingStats && firstStats && secondStats && (
            <Card>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell className="text-xs uppercase text-gray-400">Metric</TableCell>
                    <TableCell className="text-xs uppercase text-gray-400">
                      {firstStats.driver_name}
                    </TableCell>
                    <TableCell className="text-xs uppercase text-gray-400">
                      {secondStats.driver_name}
                    </TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {metrics.map((metric) => (
                    <TableRow key={metric.key}>
                      <TableCell className="text-gray-400">{metric.label}</TableCell>
                      <TableCell className="text-white">
                        {firstStats[metric.key] ?? "—"}
                      </TableCell>
                      <TableCell className="text-white">
                        {secondStats[metric.key] ?? "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          )}

          {!loadingStats && !firstStats && !secondStats && !error && (
            <Typography variant="body2" className="text-gray-500">
              Select two drivers to compare their statistics.
            </Typography>
          )}
        </div>
      )}
    </Container>
  );
}
