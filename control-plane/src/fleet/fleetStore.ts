import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { InstanceRecord, RuntimeState, WorkloadExecutionResult } from "../types";

const DEFAULT_STATE_PATH = resolve(process.cwd(), ".intelligensi_runtime.json");
const LEGACY_INSTANCE_PATH = resolve(process.cwd(), ".intelligensi_instances.json");

type LegacyDeploymentState = {
  preset?: string;
  instance_id?: string;
  ip?: string;
  container_status?: string;
  ingress_status?: string;
};

export class FleetStore {
  constructor(private readonly statePath: string = DEFAULT_STATE_PATH) {}

  loadState(): RuntimeState {
    if (!existsSync(this.statePath)) {
      return {
        version: 1,
        fleet: this.loadLegacyFleet(),
        executionHistory: [],
      };
    }

    const raw = JSON.parse(readFileSync(this.statePath, "utf8")) as RuntimeState;
    return {
      version: raw.version ?? 1,
      fleet: {
        ...this.loadLegacyFleet(),
        ...(raw.fleet ?? {}),
      },
      executionHistory: raw.executionHistory ?? [],
    };
  }

  saveState(state: RuntimeState): void {
    writeFileSync(this.statePath, JSON.stringify(state, null, 2));
  }

  upsertInstance(instance: InstanceRecord): RuntimeState {
    const state = this.loadState();
    state.fleet[instance.id] = instance;
    this.saveState(state);
    return state;
  }

  updateInstance(id: string, patch: Partial<InstanceRecord>): RuntimeState {
    const state = this.loadState();
    const current = state.fleet[id];
    if (!current) {
      throw new Error(`Unknown fleet instance: ${id}`);
    }
    state.fleet[id] = {
      ...current,
      ...patch,
      updatedAt: new Date().toISOString(),
    };
    this.saveState(state);
    return state;
  }

  appendExecution(result: WorkloadExecutionResult): RuntimeState {
    const state = this.loadState();
    state.executionHistory.unshift(result);
    state.executionHistory = state.executionHistory.slice(0, 200);
    this.saveState(state);
    return state;
  }

  private loadLegacyFleet(): Record<string, InstanceRecord> {
    if (!existsSync(LEGACY_INSTANCE_PATH)) {
      return {};
    }

    const raw = JSON.parse(readFileSync(LEGACY_INSTANCE_PATH, "utf8")) as Record<string, LegacyDeploymentState>;
    return Object.entries(raw).reduce<Record<string, InstanceRecord>>((acc, [name, value]) => {
      const providerType = name.includes("comfyui") ? "nebius" : "lambda";
      const workloadAssigned = name.includes("image-server") ? "image_generation" : undefined;
      acc[value.instance_id ?? name] = {
        id: value.instance_id ?? name,
        name,
        providerType,
        status: value.container_status === "healthy" ? "running" : "starting",
        workloadAssigned,
        publicIp: value.ip,
        endpoint: value.ip ? `http://${value.ip}:${name.includes("comfyui") ? 8188 : 8080}` : undefined,
        hourlyCostUsd: providerType === "nebius" ? 1.92 : 1.45,
        updatedAt: new Date().toISOString(),
        metadata: {
          preset: value.preset,
          ingressStatus: value.ingress_status,
        },
      };
      return acc;
    }, {});
  }
}

