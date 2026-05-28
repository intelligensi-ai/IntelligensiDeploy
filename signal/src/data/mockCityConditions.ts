import { CityConditions, LocationPoint } from "../types";

export const knownLocations: LocationPoint[] = [
  {
    name: "Aldgate",
    borough: "City of London",
    lat: 51.5145,
    lng: -0.0754,
    transportHubs: ["Aldgate", "Liverpool Street", "Elizabeth line"],
    networkBias: -7
  },
  {
    name: "Shoreditch",
    borough: "Hackney",
    lat: 51.526,
    lng: -0.078,
    transportHubs: ["Shoreditch High Street", "Liverpool Street"],
    networkBias: -5
  },
  {
    name: "Canary Wharf",
    borough: "Tower Hamlets",
    lat: 51.505,
    lng: -0.0235,
    transportHubs: ["Canary Wharf", "Elizabeth line", "Jubilee"],
    networkBias: -8
  },
  {
    name: "King's Cross",
    borough: "Camden",
    lat: 51.5308,
    lng: -0.1238,
    transportHubs: ["King's Cross St Pancras", "Northern", "Piccadilly"],
    networkBias: -6
  },
  {
    name: "Stratford",
    borough: "Newham",
    lat: 51.542,
    lng: -0.002,
    transportHubs: ["Stratford", "Elizabeth line", "Central"],
    networkBias: -6
  },
  {
    name: "South Bank",
    borough: "Lambeth",
    lat: 51.506,
    lng: -0.116,
    transportHubs: ["Waterloo", "Blackfriars"],
    networkBias: -3
  },
  {
    name: "City of London",
    borough: "City of London",
    lat: 51.513,
    lng: -0.091,
    transportHubs: ["Bank", "Monument", "Liverpool Street"],
    networkBias: -7
  },
  {
    name: "South Kensington",
    borough: "Kensington and Chelsea",
    lat: 51.494,
    lng: -0.174,
    transportHubs: ["South Kensington", "District", "Piccadilly"],
    networkBias: -1
  },
  {
    name: "Old Street",
    borough: "Islington",
    lat: 51.525,
    lng: -0.087,
    transportHubs: ["Old Street", "Northern"],
    networkBias: -4
  },
  {
    name: "Soho",
    borough: "Westminster",
    lat: 51.513,
    lng: -0.136,
    transportHubs: ["Tottenham Court Road", "Oxford Circus"],
    networkBias: -5
  },
  {
    name: "Westminster",
    borough: "Westminster",
    lat: 51.499,
    lng: -0.124,
    transportHubs: ["Westminster", "St James's Park"],
    networkBias: -2
  },
  {
    name: "Liverpool Street",
    borough: "City of London",
    lat: 51.518,
    lng: -0.081,
    transportHubs: ["Liverpool Street", "Elizabeth line", "Central"],
    networkBias: -9
  },
  {
    name: "Camden",
    borough: "Camden",
    lat: 51.539,
    lng: -0.143,
    transportHubs: ["Camden Town", "Northern"],
    networkBias: 1
  },
  {
    name: "Holborn",
    borough: "Camden",
    lat: 51.517,
    lng: -0.119,
    transportHubs: ["Holborn", "Central", "Piccadilly"],
    networkBias: -4
  },
  {
    name: "Farringdon",
    borough: "Islington",
    lat: 51.52,
    lng: -0.105,
    transportHubs: ["Farringdon", "Elizabeth line", "Thameslink"],
    networkBias: -8
  },
  {
    name: "Kensington",
    borough: "Kensington and Chelsea",
    lat: 51.501,
    lng: -0.19,
    transportHubs: ["High Street Kensington", "District"],
    networkBias: 3
  },
  {
    name: "Brixton",
    borough: "Lambeth",
    lat: 51.462,
    lng: -0.115,
    transportHubs: ["Brixton", "Victoria"],
    networkBias: 2
  },
  {
    name: "Angel",
    borough: "Islington",
    lat: 51.532,
    lng: -0.106,
    transportHubs: ["Angel", "Northern"],
    networkBias: -1
  },
  {
    name: "London Bridge",
    borough: "Southwark",
    lat: 51.505,
    lng: -0.086,
    transportHubs: ["London Bridge", "Jubilee", "Northern"],
    networkBias: -5
  },
  {
    name: "Paddington",
    borough: "Westminster",
    lat: 51.516,
    lng: -0.175,
    transportHubs: ["Paddington", "Elizabeth line", "Bakerloo"],
    networkBias: -6
  },
  {
    name: "Barbican",
    borough: "City of London",
    lat: 51.52,
    lng: -0.095,
    transportHubs: ["Barbican", "Farringdon"],
    networkBias: -6
  }
];

export const mockCityConditions: CityConditions = {
  generatedAt: "2026-05-28T16:20:00+01:00",
  cityMood: "busy after-work Thursday with strong professional networking demand",
  baselineTravelCost: 3.4,
  weatherByZone: {
    central: {
      condition: "Light rain clearing",
      rainRisk: 42,
      temperatureC: 15,
      outdoorSuitability: 67,
      weatherPenalty: 8
    },
    east: {
      condition: "Cloudy, dry intervals",
      rainRisk: 34,
      temperatureC: 16,
      outdoorSuitability: 74,
      weatherPenalty: 5
    },
    west: {
      condition: "Intermittent showers",
      rainRisk: 58,
      temperatureC: 14,
      outdoorSuitability: 55,
      weatherPenalty: 13
    },
    south: {
      condition: "Breezy with showers",
      rainRisk: 63,
      temperatureC: 14,
      outdoorSuitability: 49,
      weatherPenalty: 16
    },
    north: {
      condition: "Cool and mostly dry",
      rainRisk: 28,
      temperatureC: 15,
      outdoorSuitability: 78,
      weatherPenalty: 4
    }
  },
  disruptions: [
    {
      affectedHubs: ["Camden Town", "Northern"],
      severity: 0.18,
      message: "Minor Northern line crowding around Camden after 21:00"
    },
    {
      affectedHubs: ["Waterloo", "South Bank"],
      severity: 0.12,
      message: "South Bank footfall high due to theatre exits"
    },
    {
      affectedHubs: ["Elizabeth line"],
      severity: 0.04,
      message: "Elizabeth line running well with short platform dwell times"
    }
  ]
};
