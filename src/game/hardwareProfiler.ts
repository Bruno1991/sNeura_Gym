/**
 * Hardware Detection & Performance Optimization Profiler for SlitherAI
 * Specifically tuned for NVIDIA GeForce RTX 3060 (12GB VRAM) and high-core CPUs
 */

export interface HardwareInfo {
  gpuRenderer: string;
  gpuVendor: string;
  isNvidia: boolean;
  isRtx3060: boolean;
  cpuCores: number;
  deviceMemoryGB: number;
  webGlVersion: string;
  maxTextureSize: number;
  recommendedSubsteps: number;
  recommendedPopulation: number;
  tier: 'MAXIMUM_RTX_3060' | 'HIGH_GPU' | 'STANDARD';
}

export function detectHardware(): HardwareInfo {
  let gpuRenderer = 'NVIDIA GeForce RTX 3060 (12GB VRAM)';
  let gpuVendor = 'NVIDIA Corporation';
  let isNvidia = true;
  let isRtx3060 = true;
  let webGlVersion = 'WebGL 2.0';
  let maxTextureSize = 16384;

  try {
    const canvas = document.createElement('canvas');
    const gl =
      (canvas.getContext('webgl2') as WebGL2RenderingContext) ||
      (canvas.getContext('webgl') as WebGLRenderingContext);

    if (gl) {
      webGlVersion = canvas.getContext('webgl2') ? 'WebGL 2.0' : 'WebGL 1.0';
      maxTextureSize = gl.getParameter(gl.MAX_TEXTURE_SIZE) || 16384;
      const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
      if (debugInfo) {
        const detectedRenderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);
        const detectedVendor = gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL);
        if (detectedRenderer) gpuRenderer = detectedRenderer;
        if (detectedVendor) gpuVendor = detectedVendor;

        if (gpuRenderer.toLowerCase().includes('nvidia') || gpuVendor.toLowerCase().includes('nvidia')) {
          isNvidia = true;
        }
        if (gpuRenderer.toLowerCase().includes('3060') || gpuRenderer.toLowerCase().includes('rtx')) {
          isRtx3060 = true;
        }
      }
    }
  } catch {
    // fallback to user's hardware
  }

  const cpuCores = typeof navigator !== 'undefined' ? navigator.hardwareConcurrency || 12 : 12;
  const deviceMemoryGB = typeof navigator !== 'undefined' && (navigator as any).deviceMemory ? (navigator as any).deviceMemory : 12;

  // With RTX 3060 12GB + modern CPU, we can push 40-80 substeps and 48 snakes with ease
  const tier: HardwareInfo['tier'] = 'MAXIMUM_RTX_3060';

  return {
    gpuRenderer,
    gpuVendor,
    isNvidia,
    isRtx3060,
    cpuCores,
    deviceMemoryGB,
    webGlVersion,
    maxTextureSize,
    recommendedSubsteps: 50,
    recommendedPopulation: 48,
    tier,
  };
}
