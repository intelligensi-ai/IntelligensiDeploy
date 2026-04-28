export type WorkloadType =
  | "image_generation"
  | "video_generation"
  | "llm_inference"
  | "vector_indexing"
  | "cms_sync"
  | "background_agent"
  | "realtime_session";

export type ProviderType = "nebius" | "lambda" | "gcp";

export type InstanceStatus =
  | "provisioning"
  | "starting"
  | "running"
  | "busy"
  | "stopped"
  | "failed"
  | "destroyed";

export interface WorkloadRequirements {
  gpuRequired: boolean;
  estimatedGpuMemoryGb?: number;
  latencySensitivity?: "interactive" | "standard" | "batch";
  persistentStorageRequired?: boolean;
}

export interface WorkloadDefinition {
  id: string;
  name: string;
  type: WorkloadType;
  requirements: WorkloadRequirements;
  metadata?: Record<string, unknown>;
}

export interface RoutingContext {
  cost: "lowest" | "balanced" | "performance";
  availableCredits: Partial<Record<ProviderType, number>>;
  latencyMs?: number;
  gpuRequirement?: number;
  preferredProvider?: ProviderType;
}

export interface InstanceRecord {
  id: string;
  name: string;
  providerType: ProviderType;
  status: InstanceStatus;
  workloadAssigned?: WorkloadType;
  service?: string;
  publicIp?: string;
  endpoint?: string;
  hourlyCostUsd: number;
  estimatedMonthlyCostUsd?: number;
  metadata?: Record<string, unknown>;
  startedAt?: string;
  updatedAt: string;
}

export interface ProviderInstanceConfig {
  name: string;
  region?: string;
  zone?: string;
  gpuShape?: string;
  diskSizeGb?: number;
  persistentDisk?: boolean;
  metadata?: Record<string, unknown>;
}

export interface WorkloadDeploymentConfig {
  service: string;
  image?: string;
  mode?: "vm" | "job" | "managed";
  environment?: string;
  port?: number;
  metadata?: Record<string, unknown>;
}

export interface ProviderActionResult {
  instance: InstanceRecord;
  commands: string[];
  notes: string[];
}

export interface WorkloadExecutionResult {
  workload: WorkloadDefinition;
  providerType: ProviderType;
  routeReason: string;
  action: ProviderActionResult;
  storedAt: string;
}

export interface RuntimeState {
  version: number;
  fleet: Record<string, InstanceRecord>;
  executionHistory: WorkloadExecutionResult[];
}

