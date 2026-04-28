import { BaseProvider } from "./baseProvider";
import { InstanceRecord, ProviderActionResult, ProviderInstanceConfig, WorkloadDefinition, WorkloadDeploymentConfig } from "../types";

export class LambdaProvider extends BaseProvider {
  private readonly statusIndex = new Map<string, InstanceRecord>();

  constructor() {
    super("lambda", {
      providerType: "lambda",
      supportedWorkloads: [
        "image_generation",
        "video_generation",
        "llm_inference",
        "vector_indexing",
      ],
      reusableInstances: true,
      persistentDisk: false,
      latencyClass: "mixed",
      gpuOptimized: true,
    });
  }

  async provisionInstance(config: ProviderInstanceConfig): Promise<ProviderActionResult> {
    const id = `lambda-${config.name}`;
    const instance = this.buildInstance(id, config.name, {
      status: "provisioning",
      hourlyCostUsd: 1.45,
      estimatedMonthlyCostUsd: 1044,
      metadata: {
        region: config.region,
        gpuShape: config.gpuShape,
      },
    });
    this.statusIndex.set(id, instance);
    return this.action(instance, ["./scripts/provision_lambda_gpu.sh"], ["Lambda suits reusable GPU instances and burst workloads."]);
  }

  async startInstance(id: string): Promise<ProviderActionResult> {
    const instance = await this.getStatus(id);
    instance.status = "starting";
    instance.updatedAt = new Date().toISOString();
    this.statusIndex.set(id, instance);
    return this.action(instance, [`provider lambda start ${id}`], ["Start the Lambda GPU host or warm the execution pool."]);
  }

  async stopInstance(id: string): Promise<ProviderActionResult> {
    const instance = await this.getStatus(id);
    instance.status = "stopped";
    instance.updatedAt = new Date().toISOString();
    this.statusIndex.set(id, instance);
    return this.action(instance, [`provider lambda stop ${id}`], ["Stop the Lambda GPU instance to avoid idle cost."]);
  }

  async deployWorkload(workload: WorkloadDefinition, config: WorkloadDeploymentConfig): Promise<ProviderActionResult> {
    const id = `lambda-${config.service}-${config.environment ?? "default"}`;
    const instance = this.buildInstance(id, config.service, {
      status: "busy",
      workloadAssigned: workload.type,
      service: config.service,
      endpoint: config.port ? `http://$LAMBDA_PUBLIC_IP:${config.port}` : undefined,
      hourlyCostUsd: 1.45,
      estimatedMonthlyCostUsd: 1044,
      metadata: {
        deploymentMode: config.mode ?? "job",
        image: config.image,
      },
    });
    this.statusIndex.set(id, instance);
    return this.action(
      instance,
      ["./scripts/provision_lambda_gpu.sh", "./scripts/deploy_image_server.sh dev"],
      ["Lambda is a strong default for current image-server-style GPU execution."],
    );
  }

  async getStatus(id: string): Promise<InstanceRecord> {
    return this.statusIndex.get(id) ?? this.buildInstance(id, id, { status: "stopped", hourlyCostUsd: 1.45 });
  }

  async destroyInstance(id: string): Promise<ProviderActionResult> {
    const instance = await this.getStatus(id);
    instance.status = "destroyed";
    instance.updatedAt = new Date().toISOString();
    this.statusIndex.set(id, instance);
    return this.action(instance, ["./scripts/destroy_lambda_gpu.sh"], ["Destroy the Lambda GPU instance when the workload no longer needs reuse."]);
  }
}

