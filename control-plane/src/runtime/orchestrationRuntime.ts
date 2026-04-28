import { FleetStore } from "../fleet/fleetStore";
import { Provider } from "../providers/provider";
import { RoutingEngine } from "../router/routingEngine";
import {
  InstanceRecord,
  ProviderInstanceConfig,
  RoutingContext,
  WorkloadDefinition,
  WorkloadDeploymentConfig,
  WorkloadExecutionResult,
} from "../types";

export class OrchestrationRuntime {
  private readonly routing: RoutingEngine;

  constructor(
    private readonly providers: Provider[],
    private readonly fleetStore: FleetStore = new FleetStore(),
  ) {
    this.routing = new RoutingEngine(providers);
  }

  async triggerWorkload(
    workload: WorkloadDefinition,
    context: RoutingContext,
    instanceConfig: ProviderInstanceConfig,
    deployConfig: WorkloadDeploymentConfig,
  ): Promise<WorkloadExecutionResult> {
    const route = this.routing.resolveProvider(workload, context);
    const provider = this.providers.find((candidate) => candidate.type === route.providerType);
    if (!provider) {
      throw new Error(`Resolved provider ${route.providerType} is not registered`);
    }

    const reusable = this.findReusableInstance(route.providerType, workload.type);
    const action = reusable
      ? await provider.deployWorkload(workload, deployConfig)
      : await this.provisionAndDeploy(provider, workload, instanceConfig, deployConfig);

    this.fleetStore.upsertInstance(action.instance);
    const result: WorkloadExecutionResult = {
      workload,
      providerType: route.providerType,
      routeReason: route.reason,
      action,
      storedAt: new Date().toISOString(),
    };
    this.fleetStore.appendExecution(result);
    return result;
  }

  async startInstance(id: string): Promise<InstanceRecord> {
    const instance = this.lookupInstance(id);
    const provider = this.providerFor(instance.providerType);
    const action = await provider.startInstance(id);
    this.fleetStore.upsertInstance(action.instance);
    return action.instance;
  }

  async stopInstance(id: string): Promise<InstanceRecord> {
    const instance = this.lookupInstance(id);
    const provider = this.providerFor(instance.providerType);
    const action = await provider.stopInstance(id);
    this.fleetStore.upsertInstance(action.instance);
    return action.instance;
  }

  async destroyInstance(id: string): Promise<InstanceRecord> {
    const instance = this.lookupInstance(id);
    const provider = this.providerFor(instance.providerType);
    const action = await provider.destroyInstance(id);
    this.fleetStore.upsertInstance(action.instance);
    return action.instance;
  }

  listFleet(): Record<string, InstanceRecord> {
    return this.fleetStore.loadState().fleet;
  }

  suggestIdleShutdown(thresholdMinutes = 30): InstanceRecord[] {
    const now = Date.now();
    return Object.values(this.listFleet()).filter((instance) => {
      if (instance.status !== "running") return false;
      if (instance.providerType === "gcp") return false;
      const updated = Date.parse(instance.updatedAt);
      return !Number.isNaN(updated) && now - updated > thresholdMinutes * 60_000;
    });
  }

  private async provisionAndDeploy(
    provider: Provider,
    workload: WorkloadDefinition,
    instanceConfig: ProviderInstanceConfig,
    deployConfig: WorkloadDeploymentConfig,
  ) {
    await provider.provisionInstance(instanceConfig);
    return provider.deployWorkload(workload, deployConfig);
  }

  private findReusableInstance(providerType: InstanceRecord["providerType"], workloadAssigned?: InstanceRecord["workloadAssigned"]): InstanceRecord | undefined {
    return Object.values(this.listFleet()).find(
      (instance) =>
        instance.providerType === providerType &&
        (instance.status === "running" || instance.status === "busy") &&
        (!workloadAssigned || instance.workloadAssigned === workloadAssigned),
    );
  }

  private lookupInstance(id: string): InstanceRecord {
    const instance = this.listFleet()[id];
    if (!instance) {
      throw new Error(`Unknown instance ${id}`);
    }
    return instance;
  }

  private providerFor(providerType: InstanceRecord["providerType"]): Provider {
    const provider = this.providers.find((candidate) => candidate.type === providerType);
    if (!provider) {
      throw new Error(`Provider not registered: ${providerType}`);
    }
    return provider;
  }
}

