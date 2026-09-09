export interface Inspiration {
  id: string
  title: string
  category: string
  topic: string
  image: string
  alt: string
}

export const inspirations: readonly Inspiration[] = [
  {
    id: 'city-walk',
    title: '周末，走进一座城',
    category: '城市漫步',
    topic: '写一篇周末城市漫步图文，串联老街建筑、街角小店与沿途风景，记录步行路线和拍照灵感。',
    image: '/assets/inspiration/city.jpg',
    alt: '城市街道两旁的建筑与道路',
  },
  {
    id: 'quiet-cafe',
    title: '留给咖啡的午后',
    category: '日常生活',
    topic: '写一篇咖啡馆午后图文，从空间氛围、咖啡风味和独处体验三个角度，记录一段慢下来的日常。',
    image: '/assets/inspiration/coffee.jpg',
    alt: '咖啡倒入杯中',
  },
  {
    id: 'green-home',
    title: '窗边的一点绿意',
    category: '居家园艺',
    topic: '写一篇新手室内绿植养护图文，介绍窗边摆放、光照观察、浇水判断和常见养护误区。',
    image: '/assets/inspiration/plants.jpg',
    alt: '盆栽绿植与园艺工具',
  },
]
