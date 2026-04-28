import { BaseProvider } from "./baseProvider";
import { InstanceRecord, ProviderActionResult, ProviderInstanceConfig, WorkloadDefinition, WorkloadDeploymentConfig } from "../types";

export class NebiusProvider extends BaseProvider {
  private readonly statusIndex = new Map<string, InstanceRecord>();

  constructor() {
    super("nebius", {
      providerType: "nebius",
      supportedWorkloads: [
        "image_generation",
        "video_generation",
        "llm_inference",
        "vector_indexing",
        "background_agent",
      ],
      reusableInstances: true,
      persistentDisk: true,
      latencyClass: "mixed",
      gpuOptimized: true,
    });
  }

  async provisionInstance(config: ProviderInstanceConfig): Promise<ProviderActionResult> {
    const id = `nebius-${config.name}`;
    const instance = this.buildInstance(id, config.name, {
      status: "provisioning",
      hourlyCostUsd: 1.92,
      estimatedMonthlyCostUsd: 1382,
      metadata: {
        region: config.region,
        zone: config.zone,
        gpuShape: config.gpuShape,
        diskSizeGb: config.diskSizeGb,
        persistentDisk: config.persistentDisk ?? true,
      },
    });
    this.statusIndex.set(id, instance);
    return this.action(
      instance,
      ["./scripts/provision_nebius_gpu.sh"],
      ["Nebius uses VM + Docker + persistent disk for long-running GPU workloads."],
    );
  }

  async startInstance(id: string): Promise<ProviderActionResult> {
    const instance = await this.getStatus(id);
    instance.status = "starting";
    instance.updatedAt = new Date().toISOString();
    this.statusIndex.set(id, instance);
    return this.action(instance, [`provider nebius start ${id}`], ["Start or unfreeze the Nebius VM."]);
  }

  async stopInstance(id: string): Promise<ProviderActionResult> {
    const instance = await this.getStatus(id);
    instance.status = "stopped";
    instance.updatedAt = new Date().toISOString();
    this.statusIndex.set(id, instance);
    return this.action(instance, [`provider nebius stop ${id}`], ["Stop the Nebius VM to cut idle GPU cost."]);
  }

  async deployWorkload(workload: WorkloadDefinition, config: WorkloadDeploymentConfig): Promise<ProviderActionResult> {
    const id = `nebius-${config.service}-${config.environment ?? "default"}`;
    const instance = this.buildInstance(id, config.service, {
      status: "busy",
      workloadAssigned: workload.type,
      service: config.service,
      endpoint: config.port ? `http://$NEBIUS_PUBLIC_IP:${config.port}` : undefined,
      hourlyCostUsd: 1.92,
      estimatedMonthlyCostUsd: 1382,
      metadata: {
        deploymentMode: config.mode ?? "vm",
        image: config.image,
      },
    });
    this.statusIndex.set(id, instance);
    return this.action(
      instance,
      ["./scripts/provision_nebius_gpu.sh", `./scripts/deploy_comfyui_service.sh ${config.environment ?? "dev"}`],
      ["Best fit for ComfyUI image/video workloads that benefit from persistent GPU VMs."],
    );
  }

  async getStatus(id: string): Promise<InstanceRecord> {
    return this.statusIndex.get(id) ?? this.buildInstance(id, id, { status: "stopped", hourlyCostUsd: 1.92 });
  }

  async destroyInstance(id: string): Promise<ProviderActionResult> {
    const instance = await this.getStatus(id);
    instance.status = "destroyed";
    instance.updatedAt = new Date().toISOString();
    this.statusIndex.set(id, instance);
    return this.action(instance, ["./scripts/destroy_nebius_gpu.sh"], ["Destroy the Nebius VM and persistent attachments when no longer needed."]);
  }
}

