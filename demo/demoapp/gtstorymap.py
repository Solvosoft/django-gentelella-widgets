from djgentelella.groute import register_lookups
from djgentelella.views.storymap import BaseStoryMapGPView, BaseStoryMapMBView


@register_lookups(prefix="gigapixel_storymap", basename="examplestorymapgp")
class GigaPixelStoryMapExample(BaseStoryMapGPView):

    def get_font_css(self):
        return 'stock:opensans-gentiumbook'

    def get_storymap(self):
        return {
            "map_type": "zoomify",
            "slides": [
                {
                    "date": "",
                    "location": {
                        "icon": "http://maps.gstatic.com/intl/en_us/mapfiles/ms/micons/blue-pushpin.png",
                        "line": True
                    },
                    "background": {
                        "url": "http://gigapixel.knightlab.com/seurat/seurat_portrait.jpg",
                        "color": "#000",
                        "opacity": 50
                    },
                    "text": {
                        "headline": "A Sunday on La Grande Jatte <br><small>Georges Seurat</small>",
                        "text": "In his best-known and largest painting, Georges Seurat depicted people relaxing in a suburban park on an island in the Seine River called La Grande Jatte."
                    },
                    "type": "overview"
                },
                {
                    "date": "",
                    "location": {
                        "icon": "http://maps.gstatic.com/intl/en_us/mapfiles/ms/micons/blue-pushpin.png",
                        "lat": 75.71563324165896,
                        "line": True,
                        "lon": -132.1875,
                        "zoom": 6
                    },
                    "text": {
                        "headline": "Small Horizontal Brushstrokes",
                        "text": "Work began in 1884. The artist worked on the painting in several campaigns, beginning in 1884 with a layer of small horizontal brushstrokes of complementary colors."
                    }
                },
                {
                    "date": "",
                    "location": {
                        "icon": "http://maps.gstatic.com/intl/en_us/mapfiles/ms/micons/blue-pushpin.png",
                        "lat": 77.62241984285832,
                        "line": True,
                        "lon": -20.478515625,
                        "zoom": 4
                    },
                    "media": {
                        "caption": "",
                        "credit": "",
                        "url": ""
                    },
                    "text": {
                        "headline": "Complementary Colors",
                        "text": "The complementary colors give the painting a unified sense of color"
                    }
                },
                {
                    "date": "",
                    "location": {
                        "icon": "http://maps.gstatic.com/intl/en_us/mapfiles/ms/micons/blue-pushpin.png",
                        "lat": 77.62241984285832,
                        "line": True,
                        "lon": -20.478515625,
                        "zoom": 7
                    },
                    "media": {
                        "caption": "",
                        "credit": "",
                        "url": ""
                    },
                    "text": {
                        "headline": "Small Dots",
                        "text": "He later added small dots, also in complementary colors."
                    }
                },
                {
                    "date": "",
                    "location": {
                        "icon": "http://maps.gstatic.com/intl/en_us/mapfiles/ms/micons/blue-pushpin.png",
                        "lat": 77.62241984285832,
                        "line": True,
                        "lon": -20.478515625,
                        "zoom": 4
                    },
                    "media": {
                        "caption": "Seurat made several studies for the large painting including a smaller version. Study for La Grand Jatte, 1884. ",
                        "credit": "Georges Seurat",
                        "url": "http://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Study_for_La_Grande_Jatte%2C_Georges_Seurat%2C_1884.jpg/800px-Study_for_La_Grande_Jatte%2C_Georges_Seurat%2C_1884.jpg"
                    },
                    "text": {
                        "headline": "Dots as Solid Forms from a Distance",
                        "text": "The dots appear as solid and luminous forms when seen from a distance."
                    }
                },
                {
                    "date": "",
                    "location": {
                        "icon": "http://maps.gstatic.com/intl/en_us/mapfiles/ms/micons/blue-pushpin.png",
                        "lat": 77.63654163009744,
                        "line": True,
                        "lon": 79.62890625,
                        "zoom": 7
                    },
                    "media": {
                        "caption": "",
                        "credit": "",
                        "url": "http://en.wikipedia.org/wiki/Pointillism"
                    },
                    "text": {
                        "headline": "Pointillism",
                        "text": "Seurat's use of this highly systematic and \"scientific\" technique, subsequently called Pointillism, distinguished his art from the more intuitive approach to painting used by the Impressionists."
                    }
                },
                {
                    "date": "",
                    "location": {
                        "icon": "http://maps.gstatic.com/intl/en_us/mapfiles/ms/micons/blue-pushpin.png",
                        "lat": 72.71190310803662,
                        "line": True,
                        "lon": -9.140625,
                        "zoom": 4
                    },
                    "media": {
                        "caption": "La plage de Trouville, 1870, National Gallery, London. ",
                        "credit": "Claude Monet",
                        "url": "http://upload.wikimedia.org/wikipedia/commons/d/df/Claude_Monet_002.jpg"
                    },
                    "text": {
                        "headline": "Modern Life",
                        "text": "Although Seurat embraced the subject matter of modern life preferred by artists such as Claude Monet and Pierre-Auguste Renoir, he went beyond their concern for capturing the accidental and instantaneous qualities of light in nature."
                    }
                },
                {
                    "date": "",
                    "location": {
                        "icon": "http://maps.gstatic.com/intl/en_us/mapfiles/ms/micons/blue-pushpin.png",
                        "lat": 75.32002523220804,
                        "line": True,
                        "lon": 49.5703125,
                        "zoom": 5
                    },
                    "media": {
                        "caption": "Riace bronzes, examples of proto classic bronze sculpture",
                        "credit": "<a href='http://en.wikipedia.org/wiki/Ancient_Greek_sculpture' target='_blank'>Wikipedia</a>",
                        "url": "http://upload.wikimedia.org/wikipedia/commons/9/96/Reggio_calabria_museo_nazionale_bronzi_di_riace.jpg"
                    },
                    "text": {
                        "headline": "Permanence",
                        "text": "Seurat sought to evoke permanence by recalling the art of the past, especially Egyptian and Greek sculpture and even Italian Renaissance frescoes."
                    }
                },
                {
                    "date": "",
                    "location": {
                        "icon": "http://maps.gstatic.com/intl/en_us/mapfiles/ms/micons/blue-pushpin.png",
                        "lat": 75.45307133006602,
                        "line": True,
                        "lon": -65.126953125,
                        "zoom": 4
                    },
                    "media": {
                        "caption": "Cattle led to sacrifice, South XLV, 137–140, British Museum.",
                        "credit": "Wikipedia",
                        "url": "http://upload.wikimedia.org/wikipedia/commons/thumb/7/79/Sacrifice_south_frieze_Parthenon_BM.jpg/794px-Sacrifice_south_frieze_Parthenon_BM.jpg"
                    },
                    "text": {
                        "headline": "Procession",
                        "text": "Seurat explained to the French poet Gustave Kahn, \"The Panathenaeans of Phidias formed a procession. I want to make modern people, in their essential traits, move about as they do on those friezes, and place them on canvases organized by harmonies of color.\""
                    }
                },
                {
                    "date": "",
                    "location": {
                        "icon": "http://maps.gstatic.com/intl/en_us/mapfiles/ms/micons/blue-pushpin.png",
                        "lat": 17.14079039331665,
                        "line": True,
                        "lon": -95.44921875,
                        "zoom": 4
                    },
                    "media": {
                        "caption": "",
                        "credit": "",
                        "url": "<blockquote><p>faux Puvis de Chavannes</p><cite>Art Critic Paul Alexis</cite></blockquote>"
                    },
                    "text": {
                        "headline": "Critics",
                        "text": "Some contemporary critics, however, found his figures to be less a nod to earlier art history than a commentary on the posturing and artificiality of modern Parisian society."
                    }
                },
                {
                    "date": "",
                    "location": {
                        "icon": "http://maps.gstatic.com/intl/en_us/mapfiles/ms/micons/blue-pushpin.png",
                        "lat": -35.46066995149529,
                        "line": True,
                        "lon": -99.84374999999999,
                        "zoom": 6
                    },
                    "media": {
                        "caption": "",
                        "credit": "",
                        "url": ""
                    },
                    "text": {
                        "headline": "Frame",
                        "text": "Seurat made the final changes to La Grande Jatte in 1889. He restretched the canvas in order to add a painted border of red, orange, and blue dots that provides a visual transition between the interior of the painting and his specially designed white frame."
                    }
                },
                {
                    "date": "",
                    "location": {
                        "icon": "http://maps.gstatic.com/intl/en_us/mapfiles/ms/micons/blue-pushpin.png",
                        "lat": -30.826780904779774,
                        "line": True,
                        "lon": 128.056640625,
                        "zoom": 5
                    },
                    "media": {
                        "caption": "",
                        "credit": "",
                        "url": "http://en.wikipedia.org/wiki/Georges_Seurat"
                    },
                    "text": {
                        "headline": "Inscriptions",
                        "text": "Inscribed at lower right: Seurat"
                    }
                },
                {
                    "date": "",
                    "media": {
                        "caption": "Island of La Grande Jatte",
                        "credit": "Stamen Maps",
                        "url": "https://s3.amazonaws.com/images.m2i.stamen.com/20140221/toner_uC3-XT7eNGQ.png"
                    },
                    "text": {
                        "headline": "Info",
                        "text": "a"
                    }
                }
            ],
            "zoomify": {
                "attribution": "",
                "height": 19970,
                "path": "http://gigapixel.knightlab.com/seurat/",
                "tolerance": 0.9,
                "width": 30000
            }
        }


@register_lookups(prefix="mapbased_storymap", basename="examplestorymapmb")
class MapBasedStoryMapExample(BaseStoryMapMBView):
    def get_storymap(self):
        return {
        "slides": [{
            "type": "overview",
            "date": "",
            "text": {
                "headline": "COSTA RICA PLACES TO VISIT",
                "text": "<p>Costa Rica is a rugged, rainforested Central American country with coastlines on the Caribbean and Pacific. Though its capital, San Jose, is home to cultural institutions like the Pre-Columbian Gold Museum, Costa Rica is known for its beaches, volcanoes, and biodiversity. Roughly a quarter of its area is made up of protected jungle, teeming with wildlife including spider monkeys and quetzal birds.</p> <span class='vco-note'>This is an overview or title slide to show all the points in your story routed on your map.</span>"
            },
            "media": {
                    "url":              "https://www.worldometers.info/img/maps/costa_rica_road_map.gif",
                    "credit":               "worldometer",
                    "caption":          "Costa Rica Map"
                }
        }, {
            "date": "",
            "text": {
                "headline": "MONTEVERDE",
                "text": "<p>Monteverde is a district of the Puntarenas canton, in the Puntarenas province of Costa Rica. It is located in the Cordillera de Tilarán mountain range. Roughly a four-hour drive from the Central Valley, Monteverde is one of the country's major ecotourism destinations.</p>"
            },
            "location": {
                "name": "MONTEVERDE",
                "lat": 10.2750,
                "lon": -84.8255,
                "zoom": 10,
                "line": True
            },
            "media": {
                    "url":              "https://media.tacdn.com/media/attractions-splice-spp-674x446/0a/92/c6/e3.jpg",
                    "credit":               "viator.com",
                    "caption":          "Canopy tour in Selvatura, Monteverde."
                }
        },{
            "date": "",
            "text": {
                "headline": "MANUEL ANTONIO NATIONAL PARK",
                "text": "<p>Manuel Antonio National Park, on Costa Rica's central Pacific coast, encompasses rugged rainforest, white-sand beaches and coral reefs. It’s renowned for its vast diversity of tropical plants and wildlife, from three-toed sloths and endangered white-faced capuchin monkeys to hundreds of bird species. </p>"
            },
            "location": {
                "name": "MANUEL ANTONIO NATIONAL PARK",
                "lat": 9.3623,
                "lon": -84.1370,
                "zoom": 10,
                "line": True
            },
            "media": {
                    "url":              "https://d2xuzatlfjyc9k.cloudfront.net/wp-content/uploads/2014/05/Manuel-Antonio-National-Park-1.jpg",
                    "credit":               "costaricaexperts.com",
                    "caption":          "Manuel Antonio National Park CR."
                }
        }, {
            "date": "",
            "text": {
                "headline": "POAS VOLCANO NATIONAL PARK",
                "text": "<p>The Poás Volcano, is an active 2,697-metre stratovolcano in central Costa Rica and is located within Poas Volcano National Park. It has erupted 40 times since 1828, including April 2017 when visitors and residents were evacuated. </p>"
            },
            "location": {
                "name": "POAS VOLCANO NATIONAL PARK",
                "lat": 10.1978,
                "lon": -84.2306,
                "zoom": 10,
                "line": True
            },
            "media": {
                    "url":              "https://upload.wikimedia.org/wikipedia/commons/3/3f/Poas_crater.jpg",
                    "credit":               "wikipedia",
                    "caption":          "Poas Volcano National Park CR."
                }
        }, {
            "date": "",
            "text": {
                "headline": "TORTUGUERO",
                "text": "<p>Tortuguero is a village in Limón Province, on Costa Rica’s Caribbean coast. Part of Tortuguero National Park, it’s on a rainforest-covered sandbar whose beaches are a major nesting site for green turtles. The Sea Turtle Conservancy runs a research station and visitor center, with turtle-related exhibits. The park’s freshwater canals, wetlands and forests shelter wildlife like jaguars, tapirs and manatees. </p>"
            },
            "location": {
                "name": "TORTUGUERO",
                "lat": 10.5425,
                "lon": -83.5024,
                "zoom": 10,
                "line": True
            },
            "media": {
                    "url":              "https://dynamic-media-cdn.tripadvisor.com/media/photo-o/19/4c/15/ee/ven-a-conocer-tortuguero.jpg?w=500&h=300&s=1",
                    "credit":               "tripadvisor",
                    "caption":          "TORTUGUERO NATIONAL PARK."
                }
        }, {
            "date": "",
            "text": {
                "headline": "ARENAL VOLCANO",
                "text": "<p>Arenal Volcano is an active andesitic stratovolcano in north-western Costa Rica around 90 km northwest of San José, in the province of Alajuela, canton of San Carlos, and district of La Fortuna. The Arenal volcano measures at least 1,633 metres high. It is conically shaped with a crater 140 metres in diameter.</p>"
            },
            "location": {
                "name": "ARENAL VOLCANO",
                "lat": 10.4626,
                "lon": -84.7032,
                "zoom": 10,
                "line": True
            },
            "media": {
                    "url":              "https://upload.wikimedia.org/wikipedia/commons/5/5a/Arenal_volcano._Costa_Rica.jpg",
                    "credit":               "wikipedia",
                    "caption":          "ARENAL VOLCANO"
                }
        }]
    }
