export const resolveParams = (clip) => {
    if (clip.clipType === 'text') {
        return clip.text;
    }
    return clip.params;
};
//# sourceMappingURL=effect-params.js.map