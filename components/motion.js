export const motionEase = [0.22, 1, 0.36, 1];

export function createRowVariants(reducedMotion = false, delayChildren = 0) {
  if (reducedMotion) {
    return {
      hidden: { opacity: 1 },
      show: { opacity: 1 }
    };
  }

  return {
    hidden: { opacity: 1 },
    show: {
      opacity: 1,
      transition: {
        delayChildren,
        staggerChildren: 0.08
      }
    }
  };
}

export function createCardVariants(reducedMotion = false) {
  if (reducedMotion) {
    return {
      hidden: { opacity: 1, y: 0 },
      show: { opacity: 1, y: 0 }
    };
  }

  return {
    hidden: { opacity: 0, y: 18 },
    show: {
      opacity: 1,
      y: 0,
      transition: {
        duration: 0.45,
        ease: motionEase
      }
    }
  };
}

export function createItemVariants(reducedMotion = false, axis = "y", distance = 12) {
  const hiddenOffset = axis === "x" ? { x: distance } : { y: distance };

  if (reducedMotion) {
    return {
      hidden: { opacity: 1, x: 0, y: 0 },
      show: { opacity: 1, x: 0, y: 0 }
    };
  }

  return {
    hidden: { opacity: 0, ...hiddenOffset },
    show: {
      opacity: 1,
      x: 0,
      y: 0,
      transition: {
        duration: 0.4,
        ease: motionEase
      }
    }
  };
}

export function createHoverLift(reducedMotion = false, y = -2, scale = 1.01) {
  if (reducedMotion) {
    return {};
  }

  return {
    y,
    scale,
    transition: {
      duration: 0.18,
      ease: motionEase
    }
  };
}
