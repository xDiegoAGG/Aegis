import "dotenv/config";
import express from "express";
import cors from "cors";
import client from "prom-client";
import { useCases } from "./composition-root.js";
import { makeBooksController } from "./infrastructure/inbound/http/controllers/booksController.js";
import { makeBooksRouter } from "./infrastructure/inbound/http/routes.js";
import { startGrpcServer } from "./infrastructure/inbound/grpc/server.js";

const HTTP_PORT = Number(process.env.HTTP_PORT || 3003);
const GRPC_PORT = Number(process.env.GRPC_PORT || 50053);

const app = express();

const httpRequestDuration = new client.Histogram({
  name: "http_request_duration_seconds",
  help: "Duración de las peticiones HTTP en segundos",
  labelNames: ["method", "route", "status_code"],
  buckets: [0.01, 0.05, 0.1, 0.3, 0.5, 1, 2, 5],
});

client.collectDefaultMetrics();

app.use((req, res, next) => {
  const end = httpRequestDuration.startTimer();
  res.on("finish", () => {
    end({ method: req.method, route: req.path, status_code: res.statusCode });
  });
  next();
});

app.get("/metrics", async (_req, res) => {
  res.set("Content-Type", client.register.contentType);
  res.end(await client.register.metrics());
});

app.use(cors());
app.use(express.json());

app.get("/health", (_req, res) =>
  res.json({ status: "Ok", service: "catalog-service" })
);

app.use("/api/books", makeBooksRouter(makeBooksController(useCases)));

app.use((err, _req, res, _next) => {
  console.error(err);
  res.status(err.status || 500).json({ message: err.message || "Internal Server Error" });
});

app.listen(HTTP_PORT, () => console.log(`HTTP server listening on ${HTTP_PORT}`));
startGrpcServer({ ...useCases, port: GRPC_PORT });
