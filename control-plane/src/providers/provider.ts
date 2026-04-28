import {
  InstanceRecord,
  ProviderActionResult,
  ProviderInstanceConfig,
  ProviderType,
  RoutingContext,
  WorkloadDefinition,
  WorkloadDeploymentConfig,
  WorkloadType,
} from "../types";

export interface ProviderCapabilities {
  providerType: ProviderType;
  supportedWorkloads: WorkloadType[];
  reusableInstances: boolean;
  persistentDisk: boolean;
  latencyClass: "interactive" | "batch" | "mixed";
  gpuOptimized: boolean;
}

export interface Provider {
  readonly type: ProviderType;
  readonly capabilities: ProviderCapabilities;

  provisionInstance(config: ProviderInstanceConfig): Promise<ProviderActionResult>;
  startInstance(id: string): Promise<ProviderActionResult>;
  stopInstance(id: string): Promise<ProviderActionResult>;
  deployWorkload(workload: WorkloadDefinition, config: WorkloadDeploymentConfig): Promise<ProviderActionResult>;
  getStatus(id: string): Promise<InstanceRecord>;
  destroyInstance(id: string): Promise<ProviderActionResult>;
  scoreWorkload(workload: WorkloadDefinition, context: RoutingContext): number;
}

