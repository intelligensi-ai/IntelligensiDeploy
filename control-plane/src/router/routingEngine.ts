import { Provider } from "../providers/provider";
import { ProviderType, RoutingContext, WorkloadDefinition } from "../types";

export interface ResolvedRoute {
  providerType: ProviderType;
  score: number;
  reason: string;
}

export class RoutingEngine {
  constructor(private readonly providers: Provider[]) {}

  resolveProvider(workload: WorkloadDefinition, context: RoutingContext): ResolvedRoute {
    const scored = this.providers
      .map((provider) => ({
        providerType: provider.type,
        score: provider.scoreWorkload(workload, context),
      }))
      .sort((a, b) => b.score - a.score);

    const winner = scored[0];
    if (!winner || winner.score < 0) {
      throw new Error(`No provider can satisfy workload ${workload.type}`);
    }

    const reason = [
      `selected ${winner.providerType} for ${workload.type}`,
      `score=${winner.score}`,
      `cost=${context.cost}`,
      `gpu=${workload.requirements.gpuRequired}`,
    ].join(", ");

    return { ...winner, reason };
  }
}

