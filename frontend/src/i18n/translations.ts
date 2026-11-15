import type { Language, SampleType } from '../types/flare';

export interface TranslationBundle {
  brand: string;
  nav: {
    home: string;
    fireLab: string;
    langToggle: string;
  };
  honestyNotice: string;
  offlineMessage: string;
  home: {
    heading: string;
    searchPlaceholder: string;
    askButton: string;
    askingButton: string;
    suggestedQuestions: [string, string];
    exploreLabCta: string;
    flameHint: string;
    answerHeading: string;
    routeLabel: string;
    structuredHeading: string;
    sourcesHeading: string;
    clearAnswer: string;
  };
  lab: {
    title: string;
    resetView: string;
    controlsHeading: string;
    cursorHint: string;
    gravityLabel: string;
    gravityEarth: string;
    gravityMicrogravity: string;
    oxygenLabel: string;
    pressureLabel: string;
    airflowLabel: string;
    airflowLevels: {
      still: string;
      low: string;
      moderate: string;
      high: string;
    };
    airflowDirectionLabel: string;
    sampleTypeLabel: string;
    sampleTypes: Record<SampleType, string>;
    analyzeButton: string;
    analyzingButton: string;
    openEvidenceButton: string;
    closeEvidenceButton: string;
    resetDefaults: string;
  };
  evidence: {
    panelTitle: string;
    emptyPrompt: string;
    loadingSteps: [string, string, string, string];
    limitedEvidenceBanner: string;
    sections: {
      evidenceMatch: string;
      closestInvestigation: string;
      closestConditions: string;
      reportedBySources: string;
      interpretation: string;
      notEstablished: string;
      sources: string;
    };
    sourceRowPrefix: string;
    notSpecified: string;
  };
}

export const TRANSLATIONS: Record<Language, TranslationBundle> = {
  en: {
    brand: 'FLARE UP',
    nav: {
      home: 'Home',
      fireLab: 'Fire Lab',
      langToggle: 'العربية',
    },
    honestyNotice: 'Explore flame behavior through NASA evidence. Visuals illustrate concepts, not measured predictions.',
    offlineMessage: 'FLARE UP Evidence Engine is not connected.',
    home: {
      heading: 'How does fire behave in space?',
      searchPlaceholder: 'Ask FLARE UP about combustion in microgravity, oxygen, or airflow…',
      askButton: 'Ask FLARE UP',
      askingButton: 'Searching…',
      suggestedQuestions: [
        'How does microgravity change flame shape?',
        'How does cabin airflow influence flame spread in spacecraft?',
      ],
      exploreLabCta: 'Open 3D Fire Lab',
      flameHint: 'Move cursor across the flame to disturb airflow',
      answerHeading: 'Evidence Engine Response',
      routeLabel: 'Route',
      structuredHeading: 'Reported Experimental Records',
      sourcesHeading: 'Sources',
      clearAnswer: 'Clear',
    },
    lab: {
      title: '3D Combustion Chamber',
      resetView: 'Reset View',
      controlsHeading: 'Chamber Conditions',
      cursorHint: 'Sweep cursor near flame to create a temporary airflow disturbance · Drag to orbit',
      gravityLabel: 'Gravity',
      gravityEarth: 'Earth 1g',
      gravityMicrogravity: 'Microgravity',
      oxygenLabel: 'Oxygen Concentration',
      pressureLabel: 'Cabin Pressure',
      airflowLabel: 'Airflow Magnitude',
      airflowLevels: {
        still: 'Still',
        low: 'Low',
        moderate: 'Moderate',
        high: 'High',
      },
      airflowDirectionLabel: 'Airflow Direction',
      sampleTypeLabel: 'Sample Type',
      sampleTypes: {
        gaseous: 'Gaseous fuel',
        liquid: 'Liquid fuel',
        fabric: 'Fabric',
        polymer: 'Polymer',
      },
      analyzeButton: 'Analyze NASA Evidence',
      analyzingButton: 'Analyzing…',
      openEvidenceButton: 'NASA Evidence',
      closeEvidenceButton: 'Close Panel',
      resetDefaults: 'Reset Conditions',
    },
    evidence: {
      panelTitle: 'NASA Evidence',
      emptyPrompt: 'Adjust the chamber conditions and select “Analyze NASA Evidence” to query documented microgravity combustion records.',
      loadingSteps: [
        'Building scenario',
        'Matching NASA evidence',
        'Validating conditions',
        'Preparing explanation',
      ],
      limitedEvidenceBanner: 'Direct evidence for this exact scenario is not available.',
      sections: {
        evidenceMatch: 'Evidence Match',
        closestInvestigation: 'Closest NASA investigation',
        closestConditions: 'Closest experimental conditions',
        reportedBySources: 'Reported by Sources',
        interpretation: 'Interpretation',
        notEstablished: 'Not Established',
        sources: 'Sources',
      },
      sourceRowPrefix: 'Source',
      notSpecified: 'Not reported in retrieved records',
    },
  },
  ar: {
    brand: 'FLARE UP',
    nav: {
      home: 'الرئيسية',
      fireLab: 'مختبر اللهب',
      langToggle: 'English',
    },
    honestyNotice: 'استكشف سلوك اللهب من خلال أدلة ناسا. توضح المشاهد مفاهيم علمية، ولا تمثل تنبؤات مقاسة.',
    offlineMessage: 'FLARE UP Evidence Engine is not connected.',
    home: {
      heading: 'كيف يتصرف اللهب في الفضاء؟',
      searchPlaceholder: 'اسأل FLARE UP عن الاحتراق في الجاذبية الصغرى أو الأكسجين أو تدفق الهواء…',
      askButton: 'اسأل FLARE UP',
      askingButton: 'جارٍ البحث…',
      suggestedQuestions: [
        'كيف تؤثر الجاذبية الصغرى على شكل اللهب؟',
        'كيف يؤثر تدفق الهواء داخل المركبة على سلوك اللهب؟',
      ],
      exploreLabCta: 'افتح مختبر اللهب ثلاثي الأبعاد',
      flameHint: 'حرّك المؤشر قرب اللهب لإحداث اضطراب هوائي مؤقت',
      answerHeading: 'استجابة محرك الأدلة',
      routeLabel: 'المسار',
      structuredHeading: 'السجلات التجريبية الموثقة',
      sourcesHeading: 'المصادر',
      clearAnswer: 'مسح',
    },
    lab: {
      title: 'حجرة الاحتراق ثلاثية الأبعاد',
      resetView: 'إعادة ضبط المنظور',
      controlsHeading: 'ظروف الحجرة',
      cursorHint: 'مرّر المؤشر قرب اللهب لإحداث تيار هوائي مؤقت · اسحب لتدوير الكاميرا',
      gravityLabel: 'الجاذبية',
      gravityEarth: 'جاذبية الأرض 1g',
      gravityMicrogravity: 'جاذبية صغرى',
      oxygenLabel: 'نسبة الأكسجين',
      pressureLabel: 'الضغط',
      airflowLabel: 'شدة تدفق الهواء',
      airflowLevels: {
        still: 'ساكن',
        low: 'منخفض',
        moderate: 'متوسط',
        high: 'مرتفع',
      },
      airflowDirectionLabel: 'اتجاه تدفق الهواء',
      sampleTypeLabel: 'نوع العينة',
      sampleTypes: {
        gaseous: 'وقود غازي',
        liquid: 'وقود سائل',
        fabric: 'نسيج',
        polymer: 'بوليمر',
      },
      analyzeButton: 'تحليل أدلة ناسا',
      analyzingButton: 'جارٍ التحليل…',
      openEvidenceButton: 'أدلة ناسا',
      closeEvidenceButton: 'إغلاق اللوحة',
      resetDefaults: 'إعادة الظروف الافتراضية',
    },
    evidence: {
      panelTitle: 'أدلة ناسا الموثقة',
      emptyPrompt: 'اضبط ظروف الحجرة ثم اضغط على «تحليل أدلة ناسا» للبحث في سجلات أبحاث الاحتراق الموثقة.',
      loadingSteps: [
        'بناء السيناريو',
        'مطابقة أدلة ناسا',
        'التحقق من الظروف',
        'إعداد التفسير العلمي',
      ],
      limitedEvidenceBanner: 'Direct evidence for this exact scenario is not available.',
      sections: {
        evidenceMatch: 'تطابق الأدلة',
        closestInvestigation: 'أقرب بحث لوكالة ناسا',
        closestConditions: 'أقرب ظروف تجريبية',
        reportedBySources: 'ما ورد في المصادر',
        interpretation: 'التفسير العلمي',
        notEstablished: 'غير مثبت',
        sources: 'المصادر',
      },
      sourceRowPrefix: 'المصدر',
      notSpecified: 'غير مذكور في السجلات المسترجعة',
    },
  },
};
