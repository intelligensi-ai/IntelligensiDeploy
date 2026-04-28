import { BaseProvider } from "./baseProvider";
import { InstanceRecord, ProviderActionResult, ProviderInstanceConfig, WorkloadDefinition, WorkloadDeploymentConfig } from "../types";

export class GcpProvider extends BaseProvider {
  private readonly statusIndex = new Map<string, InstanceRecord>();

  constructor() {
    super("gcp", {
      providerType: "gcp",
      supportedWorkloads: [
        "cms_sync",
        "background_agent",
        "realtime_session",
        "vector_indexing",
        "llm_inference",
      ],
      reusableInstances: false,
      persistentDisk: false,
      latencyClass: "interactive",
      gpuOptimized: false,
    });
  }

  async provisionInstance(config: ProviderInstanceConfig): Promise<ProviderActionResult> {
    const id = `gcp-${config.name}`;
    const instance = this.buildInstance(id, config.name, {
      status: "provisioning",
      hourlyCostUsd: 0.18,
      estimatedMonthlyCostUsd: 130,
      metadata: {
        region: config.region,
        mode: "managed",
      },
    });
    this.statusIndex.set(id, instance);
    return this.action(instance, ["firebase deploy --only functions"], ["GCP is intended for lightweight compute, Firebase, and managed control-plane tasks."]);
  }

  async startInstance(id: string): Promise<ProviderActionResult> {
    const instance = await this.getStatus(id);
    instance.status = "starting";
    instance.updatedAt = new Date().toISOString();
    this.statusIndex.set(id, instance);
    return this.action(instance, [`provider gcp start ${id}`], ["Start or scale up the GCP-managed service."]);
  }

  async stopInstance(id: string): Promise<ProviderActionResult> {
    const instance = await this.getStatus(id);
    instance.status = "stopped";
    instance.updatedAt = new Date().toISOString();
    this.statusIndex.set(id, instance);
    return this.action(instance, [`provider gcp stop ${id}`], ["Scale the managed GCP service down to zero or pause it."]);
  }

  async deployWorkload(workload: WorkloadDefinition, config: WorkloadDeploymentConfig): Promise<ProviderActionResult> {
    const id = `gcp-${config.service}-${config.environment ?? "default"}`;
    const instance = this.buildInstance(id, config.service, {
      status: "busy",
      workloadAssigned: workload.type,
      service: config.service,
      hourlyCostUsd: 0.18,
      estimatedMonthlyCostUsd: 130,
      metadata: {
        deploymentMode: config.mode ?? "managed",
        image: config.image,
      },
    });
    this.statusIndex.set(id, instance);
    return this.action(
      instance,
      ["firebase deploy --only functions", "provider gcp invoke workload"],
      ["Best fit for CMS sync, background jobs, realtime sessions, and lightweight inference adjacencies."],
    );
  }

  async getStatus(id: string): Promise<InstanceRecord> {
    return this.statusIndex.get(id) ?? this.buildInstance(id, id, { status: "stopped", hourlyCostUsd: 0.18 });
  }

  async destroyInstance(id: string): Promise<ProviderActionResult> {
    const instance = await this.getStatus(id);
    instance.status = "destroyed";
    instance.updatedAt = new Date().toISOString();
    this.statusIndex.set(id, instance);
    return this.action(instance, ["provider gcp destroy managed-service"], ["Destroy or remove the managed GCP workload target."]);
  }
}

