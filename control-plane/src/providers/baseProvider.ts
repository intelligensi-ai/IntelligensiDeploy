import {
  InstanceRecord,
  ProviderActionResult,
  ProviderInstanceConfig,
  ProviderType,
  RoutingContext,
  WorkloadDefinition,
  WorkloadDeploymentConfig,
} from "../types";
import { Provider, ProviderCapabilities } from "./provider";

export abstract class BaseProvider implements Provider {
  readonly type: ProviderType;
  readonly capabilities: ProviderCapabilities;

  protected constructor(type: ProviderType, capabilities: ProviderCapabilities) {
    this.type = type;
    this.capabilities = capabilities;
  }

  abstract provisionInstance(config: ProviderInstanceConfig): Promise<ProviderActionResult>;
  abstract startInstance(id: string): Promise<ProviderActionResult>;
  abstract stopInstance(id: string): Promise<ProviderActionResult>;
  abstract deployWorkload(workload: WorkloadDefinition, config: WorkloadDeploymentConfig): Promise<ProviderActionResult>;
  abstract getStatus(id: string): Promise<InstanceRecord>;
  abstract destroyInstance(id: string): Promise<ProviderActionResult>;

  scoreWorkload(workload: WorkloadDefinition, context: RoutingContext): number {
    let score = this.capabilities.supportedWorkloads.includes(workload.type) ? 50 : -1000;

    if (context.preferredProvider === this.type) score += 30;
    if (workload.requirements.gpuRequired && this.capabilities.gpuOptimized) score += 15;
    if (workload.requirements.persistentStorageRequired && this.capabilities.persistentDisk) score += 10;
    if (context.cost === "lowest" && this.type === "gcp") score += 10;
    if (context.cost === "performance" && this.type === "nebius") score += 12;
    if (context.cost === "balanced" && this.type === "lambda") score += 8;
    if ((context.availableCredits[this.type] ?? 0) > 0) score += 6;

    if ((context.latencyMs ?? 0) <= 250 && this.capabilities.latencyClass === "interactive") score += 8;
    if ((workload.requirements.latencySensitivity ?? "standard") === "batch" && this.capabilities.latencyClass !== "interactive") {
      score += 5;
    }

    return score;
  }

  protected buildInstance(
    id: string,
    name: string,
    overrides: Partial<InstanceRecord> = {},
  ): InstanceRecord {
    return {
      id,
      name,
      providerType: this.type,
      status: "running",
      hourlyCostUsd: 0,
      updatedAt: new Date().toISOString(),
      ...overrides,
    };
  }

  protected action(instance: InstanceRecord, commands: string[], notes: string[]): ProviderActionResult {
    return { instance, commands, notes };
  }
}

